package service

import (
	"context"
	"errors"
	"log"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

type HasilChat struct {
	Jawaban       string         `json:"jawaban"`
	Sumber        []model.Sumber `json:"sumber"`
	PakaiInternet bool           `json:"pakai_internet"`
	Penjawab      string         `json:"penjawab"`
	Email         *agen.Email    `json:"-"`
}

// ErrAgentMati dipakai fitur yang hanya bisa jalan lewat agent, misalnya membaca berkas
var ErrAgentMati = errors.New("agent tidak aktif")

// JawabanAgentGagal ditampilkan jika agent aktif tetapi gagal atau terlalu lama menjawab
const JawabanAgentGagal = "Maaf, saya sedang kesulitan menyusun jawaban. Coba kirim ulang pertanyaannya sebentar lagi."

type ChatbotService struct {
	repo  *repository.PengetahuanRepository
	agen  *agen.Klien
	makna *EmbeddingService
}

// makna boleh nil; data internal lalu dicari dengan kata kunci saja
func BaruChatbotService(repo *repository.PengetahuanRepository, klienAgen *agen.Klien, makna *EmbeddingService) *ChatbotService {
	return &ChatbotService{repo: repo, agen: klienAgen, makna: makna}
}

// Jawab mencari data di database, lalu meminta agent menyusun jawaban; jika agent gagal, pakai jawaban database.
// Jika kabar diisi, jawaban agent diterima sebagai stream dan setiap status atau potongan teks diteruskan ke kabar
// tambahan berisi lampiran berkas dan izin mengirim email; boleh kosong
func (s *ChatbotService) Jawab(ctx context.Context, pertanyaan string, riwayat []agen.Riwayat, ingatan, profil string, tambahan agen.Tambahan, kabar agen.Kabar) (HasilChat, error) {
	daftar, err := s.cariData(ctx, pertanyaan)
	if err != nil {
		return HasilChat{}, err
	}

	if s.agen != nil {
		hasil, err := s.tanyaAgen(ctx, pertanyaan, daftar, riwayat, ingatan, profil, tambahan, kabar)
		if err == nil {
			return hasil, nil
		}
		log.Println("agent gagal:", err)
		return HasilChat{Jawaban: JawabanAgentGagal, Sumber: []model.Sumber{}, Penjawab: "database"}, nil
	}
	return jawabDariDatabase(daftar), nil
}

// CariPengetahuan dipakai alat cari_pengetahuan di agent untuk mencari ulang data dengan kata kunci lain
func (s *ChatbotService) CariPengetahuan(ctx context.Context, kueri string) ([]agen.Konteks, error) {
	daftar, err := s.cariData(ctx, potong(strings.TrimSpace(kueri), 300))
	if err != nil {
		return nil, err
	}
	hasil := []agen.Konteks{}
	for _, p := range daftar {
		hasil = append(hasil, agen.Konteks{Judul: p.Judul, Isi: p.Isi})
	}
	return hasil, nil
}

// BacaBerkas meneruskan berkas unggahan ke agent untuk diambil teksnya
func (s *ChatbotService) BacaBerkas(ctx context.Context, nama string, isi []byte) (agen.Berkas, error) {
	if s.agen == nil {
		return agen.Berkas{}, ErrAgentMati
	}
	return s.agen.BacaBerkas(ctx, nama, isi)
}

// cariData menggabungkan pencarian makna (embedding) dengan pencarian kata kunci; hasil makna didahulukan
// dan data yang sama tidak diambil dua kali. Jika pencarian makna gagal, kata kunci tetap dipakai
func (s *ChatbotService) cariData(ctx context.Context, pertanyaan string) ([]model.Pengetahuan, error) {
	daftar, err := s.makna.Cari(ctx, pertanyaan, 3)
	if err != nil {
		log.Println("pencarian makna gagal, pakai kata kunci saja:", err)
	}
	kataKunci, err := s.cariKataKunci(pertanyaan)
	if err != nil {
		return nil, err
	}

	dipakai := map[int]bool{}
	for _, p := range daftar {
		dipakai[p.ID] = true
	}
	for _, p := range kataKunci {
		if len(daftar) >= 4 {
			break
		}
		if !dipakai[p.ID] {
			dipakai[p.ID] = true
			daftar = append(daftar, p)
		}
	}
	return daftar, nil
}

func (s *ChatbotService) cariKataKunci(pertanyaan string) ([]model.Pengetahuan, error) {
	daftarKata := PecahKata(pertanyaan)
	if len(daftarKata) == 0 {
		return []model.Pengetahuan{}, nil
	}

	skorMinimal := 1
	if len(daftarKata) >= 3 {
		skorMinimal = 2
	}
	return s.repo.Cari(daftarKata, skorMinimal, 3)
}

func (s *ChatbotService) tanyaAgen(ctx context.Context, pertanyaan string, daftar []model.Pengetahuan, riwayat []agen.Riwayat, ingatan, profil string, tambahan agen.Tambahan, kabar agen.Kabar) (HasilChat, error) {
	konteks := []agen.Konteks{}
	for _, p := range daftar {
		konteks = append(konteks, agen.Konteks{Judul: p.Judul, Isi: p.Isi})
	}

	var jawaban agen.Jawaban
	var err error
	if kabar != nil {
		jawaban, err = s.agen.TanyaStream(ctx, pertanyaan, konteks, riwayat, ingatan, profil, tambahan, kabar)
	} else {
		jawaban, err = s.agen.Tanya(ctx, pertanyaan, konteks, riwayat, ingatan, profil, tambahan)
	}
	if err != nil {
		return HasilChat{}, err
	}

	sumber := []model.Sumber{}
	for _, sm := range jawaban.Sumber {
		sumber = append(sumber, model.Sumber{Judul: sm.Judul, URL: sm.URL})
	}

	return HasilChat{
		Jawaban:       jawaban.Jawaban,
		Sumber:        sumber,
		PakaiInternet: jawaban.PakaiInternet,
		Penjawab:      "agent",
		Email:         jawaban.Email,
	}, nil
}

func jawabDariDatabase(daftar []model.Pengetahuan) HasilChat {
	if len(daftar) == 0 {
		return HasilChat{Jawaban: "Maaf, saya belum punya informasi tentang itu.", Sumber: []model.Sumber{}, Penjawab: "database"}
	}

	// data internal tidak ditampilkan sebagai sumber
	return HasilChat{Jawaban: daftar[0].Isi, Sumber: []model.Sumber{}, Penjawab: "database"}
}
