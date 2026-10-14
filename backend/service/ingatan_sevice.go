package service

import (
	"context"
	"log"
	"strings"
	"sync"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/repository"
)

const (
	// PerbaruiIngatanSetiap: ingatan dirangkum ulang setiap sekian pertanyaan, agar LLM tidak dipanggil di tiap pesan
	PerbaruiIngatanSetiap = 4
	BatasIngatan          = 1500
)

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
