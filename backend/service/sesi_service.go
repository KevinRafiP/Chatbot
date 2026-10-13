package service

import (
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"time"

	"chatbot/backend/model"
	"chatbot/backend/repository"
)

var ErrSesiTidakValid = errors.New("sesi tidak valid")

type SesiService struct {
	repo     *repository.SesiRepository
	masa     time.Duration
	masaTamu time.Duration
}

func BaruSesiService(repo *repository.SesiRepository, masa, masaTamu time.Duration) *SesiService {
	return &SesiService{repo: repo, masa: masa, masaTamu: masaTamu}
}

// MasukTamu membuat pengguna tamu baru dan mengembalikan token untuk disimpan di perangkatnya
func (s *SesiService) MasukTamu(perangkat string) (string, model.Pengguna, error) {
	token, err := tokenBaru()
	if err != nil {
		return "", model.Pengguna{}, err
	}
	pengguna, err := s.repo.BuatTamu(hashToken(token), potongPerangkat(perangkat), time.Now().Add(s.masaTamu))
	if err != nil {
		return "", model.Pengguna{}, err
	}
	return token, pengguna, nil
}

// BuatSesi membuka sesi login untuk akun terdaftar dan mengembalikan token-nya
func (s *SesiService) BuatSesi(penggunaID, perangkat string) (string, error) {
	token, err := tokenBaru()
	if err != nil {
		return "", err
	}
	err = s.repo.BuatSesi(penggunaID, hashToken(token), potongPerangkat(perangkat), time.Now().Add(s.masa))
	return token, err
}

// Periksa mengembalikan pengguna pemilik token, atau ErrSesiTidakValid
func (s *SesiService) Periksa(token string) (model.Pengguna, error) {
	if token == "" {
		return model.Pengguna{}, ErrSesiTidakValid
	}
	pengguna, err := s.repo.CariPengguna(hashToken(token))
	if errors.Is(err, sql.ErrNoRows) {
		return model.Pengguna{}, ErrSesiTidakValid
	}
	return pengguna, err
}

// Keluar menghapus sesi login milik token
func (s *SesiService) Keluar(token string) error {
	return s.repo.Hapus(hashToken(token))
}

func tokenBaru() (string, error) {
	acak := make([]byte, 32)
	if _, err := rand.Read(acak); err != nil {
		return "", err
	}
	return hex.EncodeToString(acak), nil
}

func potongPerangkat(perangkat string) string {
	if len(perangkat) > 200 {
		return perangkat[:200]
	}
	return perangkat
}

func hashToken(token string) string {
	hasil := sha256.Sum256([]byte(token))
	return hex.EncodeToString(hasil[:])
}
