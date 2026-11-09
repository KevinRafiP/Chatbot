package service

import (
	"errors"
	"time"

	"chatbot/backend/model"
	"chatbot/backend/repository"
)

var (
	ErrJatahAkunHabis  = errors.New("jatah pemakaian harian akunmu sudah habis, coba lagi besok")
	ErrJatahSemuaHabis = errors.New("Vokapas sedang mencapai batas pemakaian harian, coba lagi nanti")
)

// JatahService membatasi token AI per 24 jam terakhir, dihitung dari catatan kinerja_jawaban,
// agar bot atau satu akun tidak menghabiskan biaya LLM. Admin tidak dibatasi
type JatahService struct {
	repo    *repository.KinerjaRepository
	perAkun int64
	semua   int64
}

// BaruJatahService mengembalikan nil bila kedua batas 0 (mati); Cek aman dipanggil pada nil
func BaruJatahService(repo *repository.KinerjaRepository, perAkun, semua int) *JatahService {
	if perAkun <= 0 && semua <= 0 {
		return nil
	}
	return &JatahService{repo: repo, perAkun: int64(perAkun), semua: int64(semua)}
}

// Cek mengembalikan ErrJatahAkunHabis atau ErrJatahSemuaHabis bila pesan baru tidak boleh dijawab lagi
func (s *JatahService) Cek(pengguna model.Pengguna) error {
	if s == nil || pengguna.Jenis == "admin" {
		return nil
	}
	sejak := time.Now().Add(-24 * time.Hour)
	if s.perAkun > 0 {
		dipakai, err := s.repo.TokenSejak(sejak, pengguna.ID)
		if err != nil {
			return err
		}
		if dipakai >= s.perAkun {
			return ErrJatahAkunHabis
		}
	}
	if s.semua > 0 {
		dipakai, err := s.repo.TokenSejak(sejak, "")
		if err != nil {
			return err
		}
		if dipakai >= s.semua {
			return ErrJatahSemuaHabis
		}
	}
	return nil
}
