package worker

import (
	"context"
	"log"
	"time"

	"chatbot/backend/repository"
	"chatbot/backend/service"
)

type PengindeksKataKunci struct {
	repo     *repository.PengetahuanRepository
	interval time.Duration
}

func BaruPengindeksKataKunci(repo *repository.PengetahuanRepository, interval time.Duration) *PengindeksKataKunci {
	return &PengindeksKataKunci{repo: repo, interval: interval}
}

// Mulai menjalankan pengindeksan sekali di awal, lalu berulang setiap interval
func (p *PengindeksKataKunci) Mulai(ctx context.Context) {
	log.Println("worker pengindeks kata kunci mulai, setiap", p.interval)
	p.jalankan()

	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println("worker pengindeks kata kunci berhenti")
			return
		case <-ticker.C:
			p.jalankan()
		}
	}
}

func (p *PengindeksKataKunci) jalankan() {
	daftar, err := p.repo.Semua()
	if err != nil {
		log.Println("worker: gagal mengambil data:", err)
		return
	}

	jumlah := 0
	for _, item := range daftar {
		kataKunciBaru := service.SusunKataKunci(item.Judul, item.Isi, item.KataKunci)
		if kataKunciBaru == item.KataKunci {
			continue
		}
		if err := p.repo.PerbaruiKataKunci(item.ID, kataKunciBaru); err != nil {
			log.Println("worker: gagal memperbarui id", item.ID, ":", err)
			continue
		}
		jumlah++
	}
	log.Println("worker: kata kunci diperbarui pada", jumlah, "data")
}
