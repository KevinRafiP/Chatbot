package service

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const (
	BatasRiwayat    = 10
	BatasPertanyaan = 2000
	BatasJudul      = 40
)

var ErrPercakapanTidakAda = errors.New("percakapan tidak ditemukan")

type HasilPesan struct {
	Judul   string      `json:"judul"`
	Pesan   model.Pesan `json:"pesan"`
	Jawaban model.Pesan `json:"jawaban"`
}

type PercakapanService struct {
	repo    *repository.PercakapanRepository
	chatbot *ChatbotService
}

func BaruPercakapanService(repo *repository.PercakapanRepository, chatbot *ChatbotService) *PercakapanService {
	return &PercakapanService{repo: repo, chatbot: chatbot}
}

func (s *PercakapanService) Daftar(penggunaID int64) ([]model.Percakapan, error) {
	return s.repo.Semua(penggunaID)
}

func (s *PercakapanService) Buat(penggunaID int64) (model.Percakapan, error) {
	return s.repo.Buat(penggunaID)
}

func (s *PercakapanService) Hapus(id, penggunaID int64) error {
	terhapus, err := s.repo.Hapus(id, penggunaID)
	if err != nil {
		return err
	}
	if !terhapus {
		return ErrPercakapanTidakAda
	}
	return nil
}

// Pesan mengambil semua pesan sebuah percakapan setelah memastikan pemiliknya
func (s *PercakapanService) Pesan(id, penggunaID int64) ([]model.Pesan, error) {
	if err := s.pastikanMilik(id, penggunaID); err != nil {
		return nil, err
	}
	return s.repo.DaftarPesan(id, 0)
}

// Kirim menyimpan pesan pengguna, meminta jawaban dengan riwayat percakapan, lalu menyimpan jawabannya
func (s *PercakapanService) Kirim(ctx context.Context, id, penggunaID int64, pertanyaan string) (HasilPesan, error) {
	pertanyaan = strings.TrimSpace(pertanyaan)
	if pertanyaan == "" || len(pertanyaan) > BatasPertanyaan {
		return HasilPesan{}, ErrDataTidakValid
	}
	if err := s.pastikanMilik(id, penggunaID); err != nil {
		return HasilPesan{}, err
	}

	lama, err := s.repo.DaftarPesan(id, BatasRiwayat)
	if err != nil {
		return HasilPesan{}, err
	}
	riwayat := []agen.Riwayat{}
	for _, p := range lama {
		riwayat = append(riwayat, agen.Riwayat{Peran: p.Pengirim, Teks: p.Isi + teksSumber(p.Sumber)})
	}

	pesan, err := s.repo.SimpanPesan(id, "user", pertanyaan, nil)
	if err != nil {
		return HasilPesan{}, err
	}

	hasil, err := s.chatbot.Jawab(ctx, pertanyaan, riwayat)
	if err != nil {
		return HasilPesan{}, err
	}

	jawaban, err := s.repo.SimpanPesan(id, "asisten", hasil.Jawaban, hasil.Sumber)
	if err != nil {
		return HasilPesan{}, err
	}

	judul := ""
	if len(lama) == 0 {
		judul = potong(pertanyaan, BatasJudul)
		if err := s.repo.UbahJudul(id, judul); err != nil {
			return HasilPesan{}, err
		}
	}
	return HasilPesan{Judul: judul, Pesan: pesan, Jawaban: jawaban}, nil
}

func (s *PercakapanService) pastikanMilik(id, penggunaID int64) error {
	milik, err := s.repo.Milik(id, penggunaID)
	if err != nil {
		return err
	}
	if !milik {
		return ErrPercakapanTidakAda
	}
	return nil
}

// teksSumber menyusun daftar sumber bernomor untuk ditempelkan ke riwayat, agar AI bisa menjawab saat ditanya sumbernya
func teksSumber(sumber []string) string {
	if len(sumber) == 0 {
		return ""
	}
	baris := []string{"\n\nSumber:"}
	for i, s := range sumber {
		baris = append(baris, fmt.Sprintf("[%d] %s", i+1, s))
	}
	return strings.Join(baris, "\n")
}

// potong memendekkan teks menjadi paling banyak n huruf
func potong(teks string, n int) string {
	huruf := []rune(teks)
	if len(huruf) <= n {
		return teks
	}
	return string(huruf[:n]) + "..."
}
