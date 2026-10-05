package worker

import (
	"context"
	"log"
	"time"

	"chatbot/backend/repository"
)

type PembersihSesi struct {
	repo     *repository.SesiRepository
	interval time.Duration
}

func BaruPembersihSesi(repo *repository.SesiRepository, interval time.Duration) *PembersihSesi {
	return &PembersihSesi{repo: repo, interval: interval}
}

// Mulai menjalankan pembersihan sekali di awal, lalu berulang setiap interval
func (p *PembersihSesi) Mulai(ctx context.Context) {
	log.Println("worker pembersih sesi mulai, setiap", p.interval)
	p.jalankan()

	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("worker pembersih sesi berhenti")
			return
		case <-ticker.C:
			p.jalankan()
		}
	}
}

func (p *PembersihSesi) jalankan() {
	sesi, tamu, err := p.repo.Bersihkan()
	if err != nil {
		log.Println("worker: gagal membersihkan sesi:", err)
		return
	}
	if sesi > 0 || tamu > 0 {
		log.Println("worker: dihapus", sesi, "sesi kedaluwarsa dan", tamu, "tamu tanpa sesi")
	}
}
