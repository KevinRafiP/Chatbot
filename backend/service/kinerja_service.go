package service

import (
	"context"
	"errors"
	"log"
	"sync/atomic"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

// ProfilRingkasan menandai catatan kinerja dari peringkasan percakapan, bukan dari jawaban
const ProfilRingkasan = "ringkasan"

// ErrKinerjaMati dipakai bila KINERJA_SIMPAN_HARI = 0
var ErrKinerjaMati = errors.New("catatan kinerja tidak aktif")

// KinerjaService mencatat lama, token, dan alat setiap panggilan AI untuk halaman kinerja admin
type KinerjaService struct {
	repo           *repository.KinerjaRepository
	simpanHari     int
	terakhirBersih atomic.Int64
}

// BaruKinerjaService mengembalikan nil bila simpanHari 0; semua method aman dipanggil pada nil
func BaruKinerjaService(repo *repository.KinerjaRepository, simpanHari int) *KinerjaService {
	if simpanHari <= 0 {
		return nil
	}
	return &KinerjaService{repo: repo, simpanHari: simpanHari}
}

// CatatPanggilan menyimpan hasil satu panggilan agent di latar belakang, jadi pengguna tidak ikut menunggu
func (s *KinerjaService) CatatPanggilan(ctx context.Context, profil string, mulai time.Time, pakai agen.Kinerja, jawaban string, err error) {
	if s == nil {
		return
	}
	k := model.Kinerja{
		Profil:         profil,
		Berhasil:       err == nil,
		LamaMs:         time.Since(mulai).Milliseconds(),
		TokenMasuk:     pakai.TokenMasuk,
		TokenKeluar:    pakai.TokenKeluar,
		PanggilanLLM:   pakai.PanggilanLLM,
		Alat:           pakai.Alat,
		PanjangJawaban: len([]rune(jawaban)),
	}
	if err != nil {
		k.Galat = potong(err.Error(), 300)
		if errors.Is(ctx.Err(), context.Canceled) {
			k.Galat = "dibatalkan pengguna"
		}
	}

	go func() {
		if err := s.repo.Simpan(k); err != nil {
			log.Println("gagal menyimpan catatan kinerja:", err)
		}
		s.bersihkan()
	}()
}

// bersihkan menghapus catatan lama paling sering sekali sehari; hanya jalan saat ada chat, jadi tidak membangunkan database
func (s *KinerjaService) bersihkan() {
	sekarang := time.Now().Unix()
	lalu := s.terakhirBersih.Load()
	if sekarang-lalu < 24*60*60 || !s.terakhirBersih.CompareAndSwap(lalu, sekarang) {
		return
	}
	if _, err := s.repo.HapusSebelum(time.Now().AddDate(0, 0, -s.simpanHari)); err != nil {
		log.Println("gagal menghapus catatan kinerja lama:", err)
	}
}

// Laporan merangkum kinerja 1, 7, atau 30 hari terakhir; nilai lain dianggap 7
func (s *KinerjaService) Laporan(hari int) (model.LaporanKinerja, error) {
	if s == nil {
		return model.LaporanKinerja{}, ErrKinerjaMati
	}
	if hari != 1 && hari != 30 {
		hari = 7
	}
	return s.repo.Laporan(hari, 10, 20)
}
