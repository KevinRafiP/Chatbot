package worker

import (
	"context"
	"log"
	"time"

	"chatbot/backend/service"
)

type PengindeksEmbedding struct {
	service  *service.EmbeddingService
	interval time.Duration
}

func BaruPengindeksEmbedding(s *service.EmbeddingService, interval time.Duration) *PengindeksEmbedding {
	return &PengindeksEmbedding{service: s, interval: interval}
}

// Mulai membuat vektor sekali di awal, lalu berulang setiap interval; tidak jalan jika pencarian makna tidak aktif
func (p *PengindeksEmbedding) Mulai(ctx context.Context) {
	if !p.service.Aktif() {
		return
	}
	log.Println("worker pengindeks embedding mulai, setiap", p.interval)
	p.jalankan(ctx)

	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("worker pengindeks embedding berhenti")
			return
		case <-ticker.C:
			p.jalankan(ctx)
		}
	}
}

func (p *PengindeksEmbedding) jalankan(ctx context.Context) {
	ctx, batal := context.WithTimeout(ctx, 5*time.Minute)
	defer batal()

	dipotong, divektor, err := p.service.Indeks(ctx)
	if dipotong > 0 || divektor > 0 {
		log.Println("worker:", dipotong, "data dipotong ulang,", divektor, "potongan dibuat vektornya")
	}
	if err != nil {
		log.Println("worker: gagal membuat embedding:", err)
	}
}
