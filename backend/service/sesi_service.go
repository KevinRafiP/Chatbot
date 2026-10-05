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
	repo *repository.SesiRepository
	masa time.Duration
}

func BaruSesiService(repo *repository.SesiRepository, masa time.Duration) *SesiService {
	return &SesiService{repo: repo, masa: masa}
}

// MasukTamu membuat pengguna tamu baru dan mengembalikan token untuk disimpan di perangkatnya
func (s *SesiService) MasukTamu(perangkat string) (string, model.Pengguna, error) {
	acak := make([]byte, 32)
	if _, err := rand.Read(acak); err != nil {
		return "", model.Pengguna{}, err
	}
	token := hex.EncodeToString(acak)

	if len(perangkat) > 200 {
		perangkat = perangkat[:200]
	}
	pengguna, err := s.repo.BuatTamu(hashToken(token), perangkat, time.Now().Add(s.masa))
	if err != nil {
		return "", model.Pengguna{}, err
	}
	return token, pengguna, nil
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

func hashToken(token string) string {
	hasil := sha256.Sum256([]byte(token))
	return hex.EncodeToString(hasil[:])
}
