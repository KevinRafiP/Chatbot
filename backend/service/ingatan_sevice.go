package service

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"chatbot/backend/agen"
	"chatbot/backend/repository"
)

const (
	// PerbaruiIngatanSetiap: ingatan dirangkum ulang setiap sekian pertanyaan, agar LLM tidak dipanggil di tiap pesan
	PerbaruiIngatanSetiap = 4
	BatasIngatan          = 1500
	// BatasInstruksi adalah panjang maksimal instruksi pribadi, dalam huruf
	BatasInstruksi = 1500
)

// ErrInstruksiPanjang dipakai bila instruksi pribadi lebih dari BatasInstruksi huruf
var ErrInstruksiPanjang = fmt.Errorf("instruksi pribadi maksimal %d huruf", BatasInstruksi)

// ErrInstruksiBerubah dipakai saat membatalkan, bila instruksi sudah diubah lagi sesudah perubahan yang mau dibatalkan
var ErrInstruksiBerubah = errors.New("instruksi pribadi sudah berubah lagi")

// IngatanService menyimpan memori jangka panjang akun: ringkasan tentang pengguna yang dibawa ke semua percakapannya
type IngatanService struct {
	repo   *repository.IngatanRepository
	agen   *agen.Klien
	sedang sync.Map
}

func BaruIngatanService(repo *repository.IngatanRepository, klienAgen *agen.Klien) *IngatanService {
	return &IngatanService{repo: repo, agen: klienAgen}
}

// Ambil mengembalikan ingatan pengguna dan apakah sudah waktunya diperbarui;
// kegagalan hanya dicatat agar chat tetap jalan tanpa ingatan
func (s *IngatanService) Ambil(penggunaID string) (string, bool) {
	ingatan, hitung, err := s.repo.Hitung(penggunaID)
	if err != nil {
		log.Println("gagal membaca ingatan:", err)
		return "", false
	}
	return ingatan, hitung%PerbaruiIngatanSetiap == 0
}

// Instruksi mengembalikan instruksi pribadi untuk dikirim ke agent; kegagalan hanya dicatat agar chat tetap jalan
func (s *IngatanService) Instruksi(penggunaID string) string {
	instruksi, err := s.repo.Instruksi(penggunaID)
	if err != nil {
		log.Println("gagal membaca instruksi pribadi:", err)
	}
	return instruksi
}

// AmbilInstruksi mengembalikan instruksi pribadi untuk ditampilkan di pengaturan akun
func (s *IngatanService) AmbilInstruksi(penggunaID string) (string, error) {
	return s.repo.Instruksi(penggunaID)
}

// SimpanInstruksi merapikan lalu menyimpan instruksi pribadi; teks kosong berarti menghapusnya
func (s *IngatanService) SimpanInstruksi(penggunaID, instruksi string) (string, error) {
	instruksi, err := rapikanInstruksi(instruksi)
	if err != nil {
		return "", err
	}
	return instruksi, s.repo.SimpanInstruksi(penggunaID, instruksi)
}

// GantiInstruksiDariChat menyimpan instruksi yang diubah lewat chat; versi sebelumnya disimpan agar bisa dibatalkan
func (s *IngatanService) GantiInstruksiDariChat(penggunaID, instruksi string) (string, error) {
	instruksi, err := rapikanInstruksi(instruksi)
	if err != nil {
		return "", err
	}
	return instruksi, s.repo.GantiInstruksiSimpanLama(penggunaID, instruksi)
}

// BatalkanInstruksi mengembalikan instruksi sebelum perubahan lewat chat. saatIni adalah instruksi hasil perubahan itu;
// jika instruksi sekarang sudah berbeda, tidak ada yang dikembalikan agar perubahan yang lebih baru tidak hilang
func (s *IngatanService) BatalkanInstruksi(penggunaID, saatIni string) (string, error) {
	saatIni, err := rapikanInstruksi(saatIni)
	if err != nil {
		return "", ErrInstruksiBerubah
	}
	instruksi, err := s.repo.KembalikanInstruksi(penggunaID, saatIni)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrInstruksiBerubah
	}
	return instruksi, err
}

func rapikanInstruksi(instruksi string) (string, error) {
	instruksi = strings.TrimSpace(strings.ReplaceAll(instruksi, "\r\n", "\n"))
	if utf8.RuneCountInString(instruksi) > BatasInstruksi {
		return "", ErrInstruksiPanjang
	}
	return instruksi, nil
}

// PerbaruiNanti merangkum percakapan terbaru ke dalam ingatan di latar belakang, jadi pengguna tidak ikut menunggu
func (s *IngatanService) PerbaruiNanti(penggunaID, ingatanLama string, riwayat []agen.Riwayat) {
	if s.agen == nil {
		return
	}
	// satu pengguna hanya boleh punya satu proses rangkum yang berjalan
	if _, berjalan := s.sedang.LoadOrStore(penggunaID, true); berjalan {
		return
	}

	pendek := []agen.Riwayat{}
	for _, r := range riwayat {
		pendek = append(pendek, agen.Riwayat{Peran: r.Peran, Teks: potong(r.Teks, 1000)})
	}

	go func() {
		defer s.sedang.Delete(penggunaID)
		ctx, batal := context.WithTimeout(context.Background(), 2*time.Minute)
		defer batal()

		baru, err := s.agen.Ringkas(ctx, ingatanLama, pendek)
		if err != nil {
			log.Println("gagal merangkum ingatan:", err)
			return
		}
		if err := s.repo.Simpan(penggunaID, potong(strings.TrimSpace(baru), BatasIngatan)); err != nil {
			log.Println("gagal menyimpan ingatan:", err)
		}
	}()
}
