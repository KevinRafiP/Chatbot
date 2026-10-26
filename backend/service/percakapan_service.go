package service

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const (
	BatasRiwayat     = 10
	BatasPertanyaan  = 2000
	BatasJudul       = 40
	BatasJudulManual = 100
)

var (
	ErrPercakapanTidakAda = errors.New("percakapan tidak ditemukan")
	ErrJudulTidakValid    = errors.New("judul tidak valid")
	ErrPesanTidakAda      = errors.New("pesan tidak ditemukan")
	BatasFavorit          = 200
)

type HasilPesan struct {
	Judul   string      `json:"judul"`
	Pesan   model.Pesan `json:"pesan"`
	Jawaban model.Pesan `json:"jawaban"`
}

type PercakapanService struct {
	repo    *repository.PercakapanRepository
	chatbot *ChatbotService
	ingatan *IngatanService
	email   *EmailJawabanService
}

// email boleh nil; jawaban lalu tidak bisa dikirim ke email
func BaruPercakapanService(repo *repository.PercakapanRepository, chatbot *ChatbotService, ingatan *IngatanService, email *EmailJawabanService) *PercakapanService {
	return &PercakapanService{repo: repo, chatbot: chatbot, ingatan: ingatan, email: email}
}

func (s *PercakapanService) Daftar(penggunaID string) ([]model.Percakapan, error) {
	return s.repo.Semua(penggunaID)
}

func (s *PercakapanService) Buat(penggunaID string) (model.Percakapan, error) {
	return s.repo.Buat(penggunaID)
}

func (s *PercakapanService) Hapus(id, penggunaID string) error {
	terhapus, err := s.repo.Hapus(id, penggunaID)
	if err != nil {
		return err
	}
	if !terhapus {
		return ErrPercakapanTidakAda
	}
	return nil
}

// GantiNama mengganti judul percakapan dengan judul pilihan pengguna
func (s *PercakapanService) GantiNama(id, penggunaID, judul string) (model.Percakapan, error) {
	judul = strings.TrimSpace(judul)
	if judul == "" || len([]rune(judul)) > BatasJudulManual {
		return model.Percakapan{}, ErrJudulTidakValid
	}
	hasil, err := s.repo.GantiJudul(id, penggunaID, judul)
	if errors.Is(err, sql.ErrNoRows) {
		return model.Percakapan{}, ErrPercakapanTidakAda
	}
	return hasil, err
}

// Pesan mengambil semua pesan sebuah percakapan setelah memastikan pemiliknya
func (s *PercakapanService) Pesan(id, penggunaID string) ([]model.Pesan, error) {
	if err := s.pastikanMilik(id, penggunaID); err != nil {
		return nil, err
	}
	return s.repo.DaftarPesan(id, 0)
}

// profilPengguna memilih profil agent dari mode pilihan pengguna; selain "cepat" dianggap "mendalam"
func profilPengguna(mode string) string {
	if mode == agen.ProfilCepat {
		return agen.ProfilCepat
	}
	return agen.ProfilMendalam
}

// Kirim menyimpan pesan pengguna, meminta jawaban dengan riwayat percakapan, lalu menyimpan jawabannya.
// mode adalah pilihan pengguna ("cepat" atau "mendalam"); kabar boleh nil, jika diisi status dan potongan teks diteruskan.
// lampiran boleh nil; bila kosong, berkas terakhir di percakapan ini tetap dipakai untuk pertanyaan lanjutan
func (s *PercakapanService) Kirim(ctx context.Context, id string, pengguna model.Pengguna, pertanyaan, mode string, lampiran *model.Lampiran, kabar agen.Kabar) (HasilPesan, error) {
	penggunaID := pengguna.ID
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

	baru := model.Lampiran{}
	if l := bersihkanLampiran(lampiran); l != nil {
		baru = *l
	}
	berkas := baru
	if baru.Teks == "" {
		if berkas, err = s.repo.LampiranTerakhir(id, BatasRiwayat); err != nil {
			return HasilPesan{}, err
		}
	}

	pesan, err := s.repo.SimpanPesanLampiran(id, "user", pertanyaan, nil, baru)
	if err != nil {
		return HasilPesan{}, err
	}

	ingatan, waktunya := s.ingatan.Ambil(penggunaID)
	tambahan := agen.Tambahan{Lampiran: lampiranAgen(&berkas), BisaEmail: s.email.Bisa(pengguna)}
	hasil, err := s.chatbot.Jawab(ctx, pertanyaan, riwayat, ingatan, profilPengguna(mode), tambahan, kabar)
	if err != nil {
		return HasilPesan{}, err
	}
	if hasil.Email != nil && tambahan.BisaEmail {
		if err := s.email.Kirim(pengguna, hasil.Email); err != nil {
			log.Println("gagal mengirim jawaban ke email:", err)
			hasil.Jawaban += "\n\n*Email belum terkirim: " + alasanEmail(err) + ".*"
		}
	}
	jawaban, err := s.repo.SimpanPesan(id, "asisten", hasil.Jawaban, hasil.Sumber)
	if err != nil {
		return HasilPesan{}, err
	}

	if waktunya {
		terbaru := append(riwayat, agen.Riwayat{Peran: "user", Teks: pertanyaan}, agen.Riwayat{Peran: "asisten", Teks: hasil.Jawaban})
		s.ingatan.PerbaruiNanti(penggunaID, ingatan, terbaru)
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

// TandaiFavorit memberi atau melepas bintang pada pesan milik pengguna
func (s *PercakapanService) TandaiFavorit(pesanID, penggunaID string, favorit bool) error {
	berubah, err := s.repo.UbahFavorit(pesanID, penggunaID, favorit)
	if err != nil {
		return err
	}
	if !berubah {
		return ErrPesanTidakAda
	}
	return nil
}

// Favorit mengambil pesan berbintang milik pengguna, paling banyak BatasFavorit pesan
func (s *PercakapanService) Favorit(penggunaID string) ([]model.PesanFavorit, error) {
	return s.repo.DaftarFavorit(penggunaID, BatasFavorit)
}

func (s *PercakapanService) pastikanMilik(id, penggunaID string) error {
	milik, err := s.repo.Milik(id, penggunaID)
	if err != nil {
		return err
	}
	if !milik {
		return ErrPercakapanTidakAda
	}
	return nil
}

// alasanEmail mengubah galat pengiriman menjadi kalimat yang aman ditampilkan ke pengguna
func alasanEmail(err error) string {
	if errors.Is(err, ErrJatahEmailHabis) {
		return "jatah kirim email hari ini sudah habis"
	}
	return "layanan email sedang bermasalah, coba lagi nanti"
}

// teksSumber menyusun daftar sumber bernomor untuk ditempelkan ke riwayat, agar AI bisa menjawab saat ditanya sumbernya
func teksSumber(sumber []model.Sumber) string {
	if len(sumber) == 0 {
		return ""
	}
	baris := []string{"\n\nSumber:"}
	for i, s := range sumber {
		baris = append(baris, strings.TrimSpace(fmt.Sprintf("[%d] %s %s", i+1, s.Judul, s.URL)))
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
