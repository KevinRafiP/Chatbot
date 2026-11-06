package service

import (
	"context"
	"errors"
	"log"
	"regexp"
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

// ErrRentangSalah dipakai bila tanggal akhir tidak setelah tanggal awal atau rentangnya lebih dari setahun
var ErrRentangSalah = errors.New("rentang tanggal tidak valid")

// ErrAkunSalah dipakai bila pilihan akun bukan id akun, "tamu", atau "lain"
var ErrAkunSalah = errors.New("akun tidak valid")

var polaID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

// maksAkun membatasi tabel "Per akun"; halaman admin membaginya per halaman sendiri
const maksAkun = 500

// maksBarisPerHalaman menjaga satu halaman tabel "Terbaru" tetap ringan walau KINERJA_BARIS_PER_HALAMAN diisi besar
const maksBarisPerHalaman = 100

// RentangKinerja memilih waktu laporan: Hari 1, 7, atau 30 dihitung mundur dari sekarang;
// Hari 0 memakai Dari sampai sebelum Sampai (tanggal pilihan sendiri)
type RentangKinerja struct {
	Hari   int
	Dari   time.Time
	Sampai time.Time
}

// KinerjaService mencatat lama, token, dan alat setiap panggilan AI untuk halaman kinerja admin
type KinerjaService struct {
	repo           *repository.KinerjaRepository
	simpanHari     int
	tampilkanIsi   bool
	perHalaman     int
	barisAlat      int
	terakhirBersih atomic.Int64
}

// BaruKinerjaService mengembalikan nil bila simpanHari 0; semua method aman dipanggil pada nil.
// tampilkanIsi true berarti admin bisa melihat potongan pertanyaan dan jawaban yang tidak disukai pengguna;
// perHalaman adalah jumlah baris per halaman tabel "Terbaru", barisAlat jumlah baris paling banyak di daftar alat
func BaruKinerjaService(repo *repository.KinerjaRepository, simpanHari int, tampilkanIsi bool, perHalaman, barisAlat int) *KinerjaService {
	if simpanHari <= 0 {
		return nil
	}
	return &KinerjaService{repo: repo, simpanHari: simpanHari, tampilkanIsi: tampilkanIsi,
		perHalaman: min(perHalaman, maksBarisPerHalaman), barisAlat: barisAlat}
}

// CatatPanggilan menyimpan hasil satu panggilan agent di latar belakang, jadi pengguna tidak ikut menunggu.
// pengguna adalah akun yang bertanya (tamu juga punya akun sementara); isi pertanyaannya tidak disimpan
func (s *KinerjaService) CatatPanggilan(ctx context.Context, pengguna model.Pengguna, profil string, mulai time.Time, pakai agen.Kinerja, jawaban string, err error) {
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
		PenggunaID:     pengguna.ID,
		JenisAkun:      pengguna.Jenis,
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

// hitungRentang mengubah pilihan admin menjadi waktu awal dan akhir (akhir tidak ikut); Hari selain 1 dan 30 dianggap 7
func hitungRentang(rentang *RentangKinerja) (dari, sampai time.Time, err error) {
	if rentang.Hari == 0 {
		if !rentang.Sampai.After(rentang.Dari) || rentang.Sampai.Sub(rentang.Dari) > 366*24*time.Hour {
			return dari, sampai, ErrRentangSalah
		}
		return rentang.Dari, rentang.Sampai, nil
	}
	if rentang.Hari != 1 && rentang.Hari != 30 {
		rentang.Hari = 7
	}
	sampai = time.Now()
	return sampai.AddDate(0, 0, -rentang.Hari), sampai, nil
}

// periksaAkun menerima akun kosong (semua akun), "tamu", "lain", atau id akun
func periksaAkun(akun string) error {
	if akun == "" || akun == repository.AkunTamu || akun == repository.AkunLain || polaID.MatchString(akun) {
		return nil
	}
	return ErrAkunSalah
}

// Laporan merangkum kinerja 1, 7, atau 30 hari terakhir, atau rentang tanggal pilihan sendiri;
// akun menyaring satu akun (kosong = semua), tetapi tabel "Per akun" selalu berisi semua akun
func (s *KinerjaService) Laporan(rentang RentangKinerja, akun string) (model.LaporanKinerja, error) {
	if s == nil {
		return model.LaporanKinerja{}, ErrKinerjaMati
	}
	if err := periksaAkun(akun); err != nil {
		return model.LaporanKinerja{}, err
	}
	dari, sampai, err := hitungRentang(&rentang)
	if err != nil {
		return model.LaporanKinerja{}, err
	}

	laporan, err := s.repo.Laporan(dari, sampai, akun, s.barisAlat)
	if err != nil {
		return laporan, err
	}
	laporan.Hari, laporan.Dari, laporan.Sampai, laporan.Akun = rentang.Hari, dari, sampai, akun
	if laporan.PerAkun, err = s.repo.PerAkun(dari, sampai, maksAkun); err != nil {
		return laporan, err
	}
	if laporan.Penilaian, err = s.repo.Penilaian(dari, sampai, akun); err != nil {
		return laporan, err
	}
	if s.tampilkanIsi {
		laporan.TidakDisukai, err = s.repo.TidakDisukai(dari, sampai, akun, 10)
	}
	return laporan, err
}

// Terbaru mengambil satu halaman tabel "Terbaru" (mulai dari 1); halaman di luar batas diganti halaman pertama atau terakhir
func (s *KinerjaService) Terbaru(rentang RentangKinerja, akun string, halaman int) (model.HalamanKinerja, error) {
	if s == nil {
		return model.HalamanKinerja{}, ErrKinerjaMati
	}
	if err := periksaAkun(akun); err != nil {
		return model.HalamanKinerja{}, err
	}
	dari, sampai, err := hitungRentang(&rentang)
	if err != nil {
		return model.HalamanKinerja{}, err
	}

	hasil := model.HalamanKinerja{PerHalaman: s.perHalaman}
	if hasil.Total, err = s.repo.Jumlah(dari, sampai, akun); err != nil {
		return hasil, err
	}
	halamanTerakhir := max(1, (hasil.Total+s.perHalaman-1)/s.perHalaman)
	hasil.Halaman = min(max(halaman, 1), halamanTerakhir)
	hasil.Baris, err = s.repo.Terbaru(dari, sampai, akun, s.perHalaman, (hasil.Halaman-1)*s.perHalaman)
	return hasil, err
}
