package service

import (
	"errors"
	"fmt"
	"strings"
	"unicode/utf8"

	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const BatasBatch = 100

var ErrDataTidakValid = errors.New("data tidak valid")

type DataMasuk struct {
	Judul     string `json:"judul"`
	Isi       string `json:"isi"`
	KataKunci string `json:"kata_kunci"`
}

type HasilPerData struct {
	Urutan int    `json:"urutan"`
	Judul  string `json:"judul"`
	ID     int    `json:"id,omitempty"`
	Status string `json:"status"`
	Pesan  string `json:"pesan,omitempty"`
}

type RingkasanBatch struct {
	Berhasil int            `json:"berhasil"`
	Gagal    int            `json:"gagal"`
	Rincian  []HasilPerData `json:"rincian"`
}

type IngestionService struct {
	repo *repository.PengetahuanRepository
}

func BaruIngestionService(repo *repository.PengetahuanRepository) *IngestionService {
	return &IngestionService{repo: repo}
}

// Simpan memeriksa, merapikan, lalu menyimpan satu data pengetahuan
func (s *IngestionService) Simpan(data DataMasuk) (model.Pengetahuan, error) {
	judul := strings.TrimSpace(data.Judul)
	isi := strings.TrimSpace(data.Isi)

	if judul == "" {
		return model.Pengetahuan{}, fmt.Errorf("%w: judul wajib diisi", ErrDataTidakValid)
	}
	if utf8.RuneCountInString(judul) > 200 {
		return model.Pengetahuan{}, fmt.Errorf("%w: judul maksimal 200 karakter", ErrDataTidakValid)
	}
	if isi == "" {
		return model.Pengetahuan{}, fmt.Errorf("%w: isi wajib diisi", ErrDataTidakValid)
	}

	p := model.Pengetahuan{
		Judul:     judul,
		Isi:       isi,
		KataKunci: SusunKataKunci(judul, isi, data.KataKunci),
	}
	return s.repo.Simpan(p)
}

// SimpanBanyak menyimpan data satu per satu dan mencatat hasil masing-masing
func (s *IngestionService) SimpanBanyak(daftar []DataMasuk) RingkasanBatch {
	ringkasan := RingkasanBatch{Rincian: []HasilPerData{}}

	for i, data := range daftar {
		hasil := HasilPerData{Urutan: i + 1, Judul: data.Judul}

		tersimpan, err := s.Simpan(data)
		if err != nil {
			hasil.Status = "gagal"
			hasil.Pesan = pesanAman(err)
			ringkasan.Gagal++
		} else {
			hasil.Status = "tersimpan"
			hasil.ID = tersimpan.ID
			ringkasan.Berhasil++
		}
		ringkasan.Rincian = append(ringkasan.Rincian, hasil)
	}
	return ringkasan
}

func pesanAman(err error) string {
	if errors.Is(err, ErrDataTidakValid) {
		return err.Error()
	}
	return "gagal menyimpan ke database"
}
