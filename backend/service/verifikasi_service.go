package service

import (
	"database/sql"
	"errors"
	"log"
	"strings"
	"time"

	"chatbot/backend/model"
)

var (
	ErrEmailBelumDiverifikasi = errors.New("email belum diverifikasi, cek kotak masuk atau folder spam")
	ErrTokenVerifikasiSalah   = errors.New("link verifikasi salah atau sudah kedaluwarsa")
	ErrGagalKirimEmail        = errors.New("email verifikasi gagal dikirim, coba kirim ulang sebentar lagi")
)

const (
	masaVerifikasi = 24 * time.Hour
	jedaKirimUlang = time.Minute
)

// PengirimEmail adalah layanan yang mengirim email teks, misalnya Brevo
type PengirimEmail interface {
	Kirim(ke, subjek, isiTeks string) error
}

// Verifikasi memakai token dari link email, menandai email-nya terverifikasi, lalu langsung membuka sesi.
// ingat ikut dikembalikan agar browser tahu pilihan "Ingat saya" saat mendaftar
func (s *AkunService) Verifikasi(token, tokenTamu, perangkat string) (string, model.Pengguna, bool, error) {
	if token == "" {
		return "", model.Pengguna{}, false, ErrTokenVerifikasiSalah
	}
	pengguna, ingat, err := s.repo.PakaiVerifikasi(hashToken(token))
	if errors.Is(err, sql.ErrNoRows) {
		return "", model.Pengguna{}, false, ErrTokenVerifikasiSalah
	}
	if err != nil {
		return "", model.Pengguna{}, false, err
	}
	tokenSesi, pengguna, err := s.bukaSesi(pengguna, tokenTamu, perangkat, ingat)
	return tokenSesi, pengguna, ingat, err
}

// KirimUlang mengirim link verifikasi baru. Email yang belum terdaftar atau sudah terverifikasi
// tetap dianggap sukses agar orang lain tidak bisa mengecek email mana yang terdaftar
func (s *AkunService) KirimUlang(email string, ingat bool) error {
	if s.pengirim == nil {
		return nil
	}
	pengguna, _, err := s.repo.CariEmail(strings.ToLower(strings.TrimSpace(email)))
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	if pengguna.Terverifikasi {
		return nil
	}
	// jeda 1 menit mencegah kotak masuk dibanjiri dan kuota Brevo habis
	if waktu, err := s.repo.TerakhirDikirim(pengguna.ID); err == nil && time.Since(waktu) < jedaKirimUlang {
		return nil
	}
	return s.kirimVerifikasi(pengguna, ingat)
}

// kirimVerifikasi membuat token baru (token lama tidak berlaku lagi) lalu mengirim link-nya ke email akun
func (s *AkunService) kirimVerifikasi(pengguna model.Pengguna, ingat bool) error {
	token, err := tokenBaru()
	if err != nil {
		return err
	}
	if err := s.repo.SimpanVerifikasi(pengguna.ID, hashToken(token), ingat, time.Now().Add(masaVerifikasi)); err != nil {
		return err
	}

	link := s.alamatFrontend + "/?verifikasi=" + token
	isi := "Halo " + pengguna.Nama + ",\n\n" +
		"Klik link berikut untuk memverifikasi email akun Vokapas kamu:\n" + link + "\n\n" +
		"Link berlaku 24 jam. Abaikan email ini jika kamu tidak merasa mendaftar."
	if err := s.pengirim.Kirim(pengguna.Email, "Verifikasi email akun Vokapas", isi); err != nil {
		log.Println("gagal kirim email verifikasi:", err)
		return ErrGagalKirimEmail
	}
	return nil
}
