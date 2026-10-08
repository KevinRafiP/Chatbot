package service

import (
	"context"
	"log"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

type HasilChat struct {
	Jawaban       string         `json:"jawaban"`
	Sumber        []model.Sumber `json:"sumber"`
	PakaiInternet bool           `json:"pakai_internet"`
	Penjawab      string         `json:"penjawab"`
}

type ChatbotService struct {
	repo *repository.PengetahuanRepository
	agen *agen.Klien
}

func BaruChatbotService(repo *repository.PengetahuanRepository, klienAgen *agen.Klien) *ChatbotService {
	return &ChatbotService{repo: repo, agen: klienAgen}
}

// Jawab mencari data di database, lalu meminta agent menyusun jawaban; jika agent gagal, pakai jawaban database
func (s *ChatbotService) Jawab(ctx context.Context, pertanyaan string, riwayat []agen.Riwayat) (HasilChat, error) {
	daftar, err := s.cariData(pertanyaan)
	if err != nil {
		return HasilChat{}, err
	}

	if s.agen != nil {
		hasil, err := s.tanyaAgen(ctx, pertanyaan, daftar, riwayat)
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

	skorMinimal := 1
	if len(daftarKata) >= 3 {
		skorMinimal = 2
	}
	return s.repo.Cari(daftarKata, skorMinimal, 3)
}

func (s *ChatbotService) tanyaAgen(ctx context.Context, pertanyaan string, daftar []model.Pengetahuan, riwayat []agen.Riwayat) (HasilChat, error) {
	konteks := []agen.Konteks{}
	for _, p := range daftar {
		konteks = append(konteks, agen.Konteks{Judul: p.Judul, Isi: p.Isi})
	}

	jawaban, err := s.agen.Tanya(ctx, pertanyaan, konteks, riwayat)
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
	}, nil
}

func jawabDariDatabase(daftar []model.Pengetahuan) HasilChat {
	if len(daftar) == 0 {
		return HasilChat{Jawaban: "Maaf, saya belum punya informasi tentang itu.", Sumber: []model.Sumber{}, Penjawab: "database"}
	}

	sumber := []model.Sumber{{Judul: daftar[0].Judul}}
	return HasilChat{Jawaban: daftar[0].Isi + " [1]", Sumber: sumber, Penjawab: "database"}
}
