package service

import (
	"context"
	"log"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

type HasilChat struct {
	Jawaban       string   `json:"jawaban"`
	Sumber        []string `json:"sumber"`
	PakaiInternet bool     `json:"pakai_internet"`
	Penjawab      string   `json:"penjawab"`
}

type ChatbotService struct {
	repo *repository.PengetahuanRepository
	agen *agen.Klien
}

func BaruChatbotService(repo *repository.PengetahuanRepository, klienAgen *agen.Klien) *ChatbotService {
	return &ChatbotService{repo: repo, agen: klienAgen}
}

// Jawab mencari data di database, lalu meminta agent menyusun jawaban; jika agent gagal, pakai jawaban database
func (s *ChatbotService) Jawab(ctx context.Context, pertanyaan string) (HasilChat, error) {
	daftar, err := s.cariData(pertanyaan)
	if err != nil {
		return HasilChat{}, err
	}

	if s.agen != nil {
		hasil, err := s.tanyaAgen(ctx, pertanyaan, daftar)
		if err == nil {
			return hasil, nil
		}
		log.Println("agent gagal, pakai jawaban database:", err)
	}
	return jawabDariDatabase(daftar), nil
}

func (s *ChatbotService) cariData(pertanyaan string) ([]model.Pengetahuan, error) {
	daftarKata := PecahKata(pertanyaan)
	if len(daftarKata) == 0 {
		return []model.Pengetahuan{}, nil
	}
	return s.repo.Cari(daftarKata, 3)
}

func (s *ChatbotService) tanyaAgen(ctx context.Context, pertanyaan string, daftar []model.Pengetahuan) (HasilChat, error) {
	konteks := []agen.Konteks{}
	sumber := []string{}
	for _, p := range daftar {
		konteks = append(konteks, agen.Konteks{Judul: p.Judul, Isi: p.Isi})
		sumber = append(sumber, p.Judul)
	}

	jawaban, err := s.agen.Tanya(ctx, pertanyaan, konteks)
	if err != nil {
		return HasilChat{}, err
	}

	for _, sm := range jawaban.Sumber {
		sumber = append(sumber, sm.URL)
	}
	return HasilChat{
		Jawaban:       jawaban.Jawaban,
		Sumber:        sumber,
		PakaiInternet: jawaban.PakaiInternet,
		Penjawab:      "agent",
	}, nil
}

func jawabDariDatabase(daftar []model.Pengetahuan) HasilChat {
	if len(daftar) == 0 {
		return HasilChat{Jawaban: "Maaf, saya belum punya informasi tentang itu.", Sumber: []string{}, Penjawab: "database"}
	}

	sumber := []string{}
	for _, p := range daftar {
		sumber = append(sumber, p.Judul)
	}
	return HasilChat{Jawaban: daftar[0].Isi, Sumber: sumber, Penjawab: "database"}
}
