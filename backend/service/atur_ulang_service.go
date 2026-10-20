package service

import (
	"database/sql"
	"errors"
	"log"
	"strings"
	"time"

	"golang.org/x/crypto/bcrypt"

	"chatbot/backend/model"
)

var (
	ErrTokenAturUlangSalah = errors.New("link atur ulang password salah atau sudah kedaluwarsa")
	ErrEmailTidakAktif     = errors.New("pengiriman email belum aktif, lupa password belum bisa dipakai")
	ErrGagalKirimAturUlang = errors.New("email atur ulang password gagal dikirim, coba lagi sebentar lagi")
)

const (
	masaAturUlang = time.Hour
	jedaAturUlang = 2 * time.Minute
)

// LupaPassword mengirim link untuk membuat password baru. Email yang belum terdaftar tetap dianggap sukses
// agar orang lain tidak bisa mengecek email mana yang terdaftar
func (s *AkunService) LupaPassword(email string) error {
	if s.pengirim == nil {
		return ErrEmailTidakAktif
	}
	pengguna, _, err := s.repo.CariEmail(strings.ToLower(strings.TrimSpace(email)))
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	// jeda 2 menit mencegah kotak masuk dibanjiri dan kuota Brevo habis
	if waktu, err := s.repo.TerakhirAturUlang(pengguna.ID); err == nil && time.Since(waktu) < jedaAturUlang {
		return nil
	}

	token, err := tokenBaru()
	if err != nil {
		return err
	}
	if err := s.repo.SimpanAturUlang(pengguna.ID, hashToken(token), time.Now().Add(masaAturUlang)); err != nil {
		return err
	}

	link := s.alamatFrontend + "/?atur-ulang=" + token
	isi := "Halo " + pengguna.Nama + ",\n\n" +
		"Klik link berikut untuk membuat password baru akun Vokapas kamu:\n" + link + "\n\n" +
		"Link berlaku 1 jam dan hanya bisa dipakai sekali. Abaikan email ini jika kamu tidak meminta ganti password, password lama tetap berlaku."
	if err := s.pengirim.Kirim(pengguna.Email, "Atur ulang password Vokapas", isi); err != nil {
		log.Println("gagal kirim email atur ulang password:", err)
		return ErrGagalKirimAturUlang
	}
	return nil
}

// AturUlangPassword mengganti password memakai token dari link email, mengeluarkan akun dari semua perangkat,
// lalu membuka sesi baru di perangkat ini. Password dicek dulu agar token tidak terpakai oleh password yang ditolak
func (s *AkunService) AturUlangPassword(token, passwordBaru, tokenTamu, perangkat string, ingat bool) (string, model.Pengguna, error) {
	if len(passwordBaru) < 8 || len(passwordBaru) > 72 {
		return "", model.Pengguna{}, ErrPasswordTidakValid
	}
	if token == "" {
		return "", model.Pengguna{}, ErrTokenAturUlangSalah
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(passwordBaru), bcrypt.DefaultCost)
	if err != nil {
		return "", model.Pengguna{}, err
	}
	pengguna, err := s.repo.PakaiAturUlang(hashToken(token), string(hash))
	if errors.Is(err, sql.ErrNoRows) {
		return "", model.Pengguna{}, ErrTokenAturUlangSalah
	}
	if err != nil {
		return "", model.Pengguna{}, err
	}
	return s.bukaSesi(pengguna, tokenTamu, perangkat, ingat)
}
