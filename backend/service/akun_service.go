package service

import (
	"database/sql"
	"errors"
	"net/mail"
	"slices"
	"strings"

	"golang.org/x/crypto/bcrypt"

	"chatbot/backend/model"
	"chatbot/backend/repository"
)

var (
	ErrEmailTidakValid    = errors.New("email tidak valid")
	ErrPasswordTidakValid = errors.New("password minimal 8 dan maksimal 72 karakter")
	ErrEmailSudahAda      = errors.New("email sudah terdaftar")
	ErrLoginSalah         = errors.New("email atau password salah")
	ErrAkunTidakAda       = errors.New("email belum terdaftar")
)

type AkunService struct {
	repo           *repository.AkunRepository
	sesi           *SesiService
	emailAdmin     []string
	pengirim       PengirimEmail
	alamatFrontend string
}

// pengirim boleh nil: akun baru langsung aktif tanpa verifikasi email
func BaruAkunService(repo *repository.AkunRepository, sesi *SesiService, emailAdmin []string,
	pengirim PengirimEmail, alamatFrontend string) *AkunService {
	daftar := []string{}
	for _, email := range emailAdmin {
		daftar = append(daftar, strings.ToLower(email))
	}
	return &AkunService{repo: repo, sesi: sesi, emailAdmin: daftar,
		pengirim: pengirim, alamatFrontend: strings.TrimRight(alamatFrontend, "/")}
}

// Daftar membuat akun baru. Bila verifikasi email aktif, token yang dikembalikan kosong dan link verifikasi dikirim;
// selain itu sesinya langsung dibuka dan percakapan tamu yang sedang dipakai ikut dipindahkan
func (s *AkunService) Daftar(email, password, tokenTamu, perangkat string, ingat bool) (string, model.Pengguna, error) {
	email, err := rapikanEmail(email)
	if err != nil {
		return "", model.Pengguna{}, err
	}
	if len(password) < 8 || len(password) > 72 {
		return "", model.Pengguna{}, ErrPasswordTidakValid
	}

	if _, _, err := s.repo.CariEmail(email); err == nil {
		return "", model.Pengguna{}, ErrEmailSudahAda
	} else if !errors.Is(err, sql.ErrNoRows) {
		return "", model.Pengguna{}, err
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return "", model.Pengguna{}, err
	}
	nama, _, _ := strings.Cut(email, "@")
	pengguna, err := s.repo.Buat(nama, email, string(hash), s.jenisUntuk(email, "user"), s.pengirim == nil)
	if err != nil {
		return "", model.Pengguna{}, err
	}
	if s.pengirim != nil {
		// email yang gagal terkirim tidak membatalkan pendaftaran; pengguna masih bisa menekan "Kirim ulang"
		if err := s.kirimVerifikasi(pengguna, ingat); err != nil && !errors.Is(err, ErrGagalKirimEmail) {
			return "", model.Pengguna{}, err
		}
		return "", pengguna, nil
	}
	return s.bukaSesi(pengguna, tokenTamu, perangkat, ingat)
}

// Masuk memeriksa email dan password, lalu membuka sesi baru
func (s *AkunService) Masuk(email, password, tokenTamu, perangkat string, ingat bool) (string, model.Pengguna, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	pengguna, hash, err := s.repo.CariEmail(email)
	if errors.Is(err, sql.ErrNoRows) {
		return "", model.Pengguna{}, ErrLoginSalah
	}
	if err != nil {
		return "", model.Pengguna{}, err
	}
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) != nil {
		return "", model.Pengguna{}, ErrLoginSalah
	}
	if s.pengirim != nil && !pengguna.Terverifikasi {
		return "", model.Pengguna{}, ErrEmailBelumDiverifikasi
	}
	if jenis := s.jenisUntuk(email, pengguna.Jenis); jenis != pengguna.Jenis {
		if _, err := s.repo.UbahJenis(email, jenis); err != nil {
			return "", model.Pengguna{}, err
		}
		pengguna.Jenis = jenis
	}
	return s.bukaSesi(pengguna, tokenTamu, perangkat, ingat)
}

// JadikanAdmin mengubah akun yang sudah terdaftar menjadi admin
func (s *AkunService) JadikanAdmin(email string) error {
	email, err := rapikanEmail(email)
	if err != nil {
		return err
	}
	ada, err := s.repo.UbahJenis(email, "admin")
	if err != nil {
		return err
	}
	if !ada {
		return ErrAkunTidakAda
	}
	return nil
}

// bukaSesi membuat token untuk akun; percakapan dari token tamu (jika ada) ikut dipindahkan
func (s *AkunService) bukaSesi(pengguna model.Pengguna, tokenTamu, perangkat string, ingat bool) (string, model.Pengguna, error) {
	if tamu, err := s.sesi.Periksa(tokenTamu); err == nil && tamu.Jenis == "tamu" {
		if err := s.repo.PindahkanPercakapan(tamu.ID, pengguna.ID); err != nil {
			return "", model.Pengguna{}, err
		}
	}
	token, err := s.sesi.BuatSesi(pengguna.ID, perangkat, ingat)
	return token, pengguna, err
}

// jenisUntuk memberi "admin" bagi email yang tercantum di ADMIN_EMAIL, selain itu jenis yang sudah ada
func (s *AkunService) jenisUntuk(email, jenisLama string) string {
	if slices.Contains(s.emailAdmin, email) {
		return "admin"
	}
	return jenisLama
}

func rapikanEmail(email string) (string, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	alamat, err := mail.ParseAddress(email)
	if err != nil || alamat.Address != email || len(email) > 254 {
		return "", ErrEmailTidakValid
	}
	return email, nil
}
