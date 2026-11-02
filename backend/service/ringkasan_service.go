package service

import (
	"context"
	"errors"
	"log"
	"strings"
	"sync"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/repository"
)

const (
	BatasRingkasan = 2000
	// MaksPesanRingkas adalah pesan terbanyak yang diringkas sekali jalan, agar permintaan ke agent tidak terlalu besar
	MaksPesanRingkas = 40
)

// RingkasanService meringkas pesan lama percakapan panjang, agar AI tetap ingat awal percakapan
// tanpa mengirim semua pesannya setiap kali bertanya
type RingkasanService struct {
	repo    *repository.PercakapanRepository
	agen    *agen.Klien
	kinerja *KinerjaService
	setelah int // jumlah pesan belum diringkas yang memicu peringkasan
	sisa    int // pesan terbaru yang tetap dikirim utuh setelah diringkas
	sedang  sync.Map
}

// BaruRingkasanService mengembalikan nil bila agent mati atau setelah 0; semua method aman dipanggil pada nil
func BaruRingkasanService(repo *repository.PercakapanRepository, klienAgen *agen.Klien, kinerja *KinerjaService, setelah, sisa int) *RingkasanService {
	if klienAgen == nil || setelah <= 0 {
		return nil
	}
	// riwayat hanya membawa BatasRiwayat pesan; batas lebih besar membuat ada pesan yang tidak terbawa sama sekali
	setelah = min(setelah, BatasRiwayat)
	if sisa >= setelah {
		sisa = setelah / 2
	}
	// genap agar pasangan pertanyaan dan jawaban tidak terpisah
	sisa -= sisa % 2
	return &RingkasanService{repo: repo, agen: klienAgen, kinerja: kinerja, setelah: setelah, sisa: sisa}
}

// Ambil mengembalikan ringkasan percakapan dan urutan pesan terakhir yang sudah diringkas;
// kegagalan hanya dicatat agar chat tetap jalan dengan riwayat biasa
func (s *RingkasanService) Ambil(id string) (string, int64) {
	if s == nil {
		return "", 0
	}
	ringkasan, sampai, err := s.repo.Ringkasan(id)
	if err != nil {
		log.Println("gagal membaca ringkasan percakapan:", err)
		return "", 0
	}
	return ringkasan, sampai
}

// PerbaruiNanti meringkas pesan lama di latar belakang bila pesan yang belum diringkas sudah mencapai batas
func (s *RingkasanService) PerbaruiNanti(id string, belumDiringkas int) {
	if s == nil || belumDiringkas < s.setelah {
		return
	}
	// satu percakapan hanya boleh punya satu proses ringkas yang berjalan
	if _, berjalan := s.sedang.LoadOrStore(id, true); berjalan {
		return
	}
	go func() {
		defer s.sedang.Delete(id)
		if err := s.perbarui(id); err != nil {
			log.Println("gagal meringkas percakapan:", err)
		}
	}()
}

func (s *RingkasanService) perbarui(id string) error {
	lama, sampai, err := s.repo.Ringkasan(id)
	if err != nil {
		return err
	}
	pesan, err := s.repo.DaftarPesanSetelah(id, sampai, 0)
	if err != nil || len(pesan) < s.setelah {
		return err
	}
	diringkas := pesan[:len(pesan)-s.sisa]
	if len(diringkas) > MaksPesanRingkas {
		diringkas = diringkas[:MaksPesanRingkas]
	}

	riwayat := []agen.Riwayat{}
	for _, p := range diringkas {
		riwayat = append(riwayat, agen.Riwayat{Peran: p.Pengirim, Teks: potong(p.Isi+teksSumber(p.Sumber), 2000)})
	}

	ctx, batal := context.WithTimeout(context.Background(), 2*time.Minute)
	defer batal()
	mulai := time.Now()
	baru, pakai, err := s.agen.RingkasPercakapan(ctx, lama, riwayat)
	s.kinerja.CatatPanggilan(ctx, ProfilRingkasan, mulai, pakai, baru, err)
	if err != nil {
		return err
	}
	if baru = strings.TrimSpace(baru); baru == "" {
		return errors.New("agent mengembalikan ringkasan kosong")
	}
	return s.repo.SimpanRingkasan(id, potong(baru, BatasRingkasan), diringkas[len(diringkas)-1].Urutan, sampai)
}
