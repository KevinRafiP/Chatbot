package service

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"log"
	"regexp"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const (
	maksPotongan   = 1000 // karakter per potongan
	ukuranKiriman  = 16   // potongan per panggilan /embed, agar body dan balasan agent tetap kecil
	maksKiriman    = 50   // panggilan /embed paling banyak dalam satu putaran worker
	maksDataUbah   = 100  // data yang dipotong ulang paling banyak dalam satu putaran worker
	batasWaktuCari = 8 * time.Second
)

var (
	polaModel        = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9./:_-]*$`)
	polaParagraf     = regexp.MustCompile(`\n\s*\n`)
	polaAkhirKalimat = regexp.MustCompile(`([.!?])\s+|\n`)
)

// EmbeddingService mengikuti pengaturan embedding di agent; model kosong berarti embedding di agent sedang mati
type EmbeddingService struct {
	repo *repository.EmbeddingRepository
	agen *agen.Klien

	kunci       sync.RWMutex
	model       string
	skorMinimal float64
}

// BaruEmbeddingService mengembalikan nil jika agent atau tabel embedding tidak ada; semua fungsinya aman dipanggil pada nil
func BaruEmbeddingService(repo *repository.EmbeddingRepository, klienAgen *agen.Klien) *EmbeddingService {
	if klienAgen == nil {
		return nil
	}
	ada, err := repo.Tersedia()
	if err != nil || !ada {
		log.Println("tabel embedding_potongan belum ada (pgvector belum terpasang): pencarian makna tidak aktif", err)
		return nil
	}
	return &EmbeddingService{repo: repo, agen: klienAgen}
}

func (s *EmbeddingService) Aktif() bool {
	return s != nil
}

// Perbarui menanyakan model embedding yang aktif di agent, lalu mencatat jika ada perubahan
func (s *EmbeddingService) Perbarui(ctx context.Context) error {
	info, err := s.agen.InfoEmbedding(ctx)
	if err != nil {
		return err
	}
	model := ""
	if info.Aktif {
		// nama model ditulis langsung di query pencarian, jadi polanya wajib diperiksa
		if !polaModel.MatchString(info.Model) {
			return fmt.Errorf("nama model embedding dari agent tidak valid: %q", info.Model)
		}
		model = info.Model
	}

	s.kunci.Lock()
	berubah := model != s.model
	s.model, s.skorMinimal = model, info.SkorMinimal
	s.kunci.Unlock()

	if berubah && model == "" {
		log.Println("embedding di agent mati: pengetahuan dicari dengan kata kunci saja")
	} else if berubah {
		log.Printf("pencarian makna aktif dengan model %s (kemiripan minimal %.2f)", model, info.SkorMinimal)
	}
	return nil
}

func (s *EmbeddingService) pengaturan() (string, float64) {
	s.kunci.RLock()
	defer s.kunci.RUnlock()
	return s.model, s.skorMinimal
}

// Cari mengambil potongan data yang maknanya paling dekat dengan pertanyaan, satu potongan terbaik per data
func (s *EmbeddingService) Cari(ctx context.Context, pertanyaan string, batas int) ([]model.Pengetahuan, error) {
	if s == nil || strings.TrimSpace(pertanyaan) == "" {
		return nil, nil
	}
	namaModel, skorMinimal := s.pengaturan()
	if namaModel == "" {
		return nil, nil
	}
	ctx, batal := context.WithTimeout(ctx, batasWaktuCari)
	defer batal()

	modelAgent, daftarVektor, err := s.agen.Embed(ctx, agen.EmbedKueri, []string{pertanyaan})
	if err != nil {
		return nil, err
	}
	if modelAgent != namaModel {
		return nil, fmt.Errorf("model embedding di agent berganti ke %q, menunggu worker", modelAgent)
	}
	// diambil lebih banyak karena satu data bisa punya beberapa potongan yang sama-sama mirip
	hasil, err := s.repo.CariMirip(namaModel, daftarVektor[0], batas*3)
	if err != nil {
		return nil, err
	}

	daftar := []model.Pengetahuan{}
	dipakai := map[int]bool{}
	tertinggi := 0.0
	for _, h := range hasil {
		tertinggi = max(tertinggi, h.Skor)
		if h.Skor < skorMinimal || dipakai[h.ID] || len(daftar) == batas {
			continue
		}
		dipakai[h.ID] = true
		daftar = append(daftar, h.Pengetahuan)
	}
	log.Printf("pencarian makna: %d data dipakai, skor tertinggi %.2f (minimal %.2f)", len(daftar), tertinggi, skorMinimal)
	return daftar, nil
}

// Indeks memotong ulang data yang baru atau berubah, lalu membuat vektor untuk potongan yang belum punya
func (s *EmbeddingService) Indeks(ctx context.Context) (dipotong, divektor int, err error) {
	if s == nil {
		return 0, 0, nil
	}
	if err := s.Perbarui(ctx); err != nil {
		return 0, 0, err
	}
	namaModel, _ := s.pengaturan()
	if namaModel == "" {
		return 0, 0, nil
	}
	daftarData, err := s.repo.PengetahuanBerubah(maksDataUbah)
	if err != nil {
		return 0, 0, err
	}
	for _, p := range daftarData {
		if err := s.repo.GantiPotongan(p.ID, Sidik(p.Judul, p.Isi), PecahPotongan(p.Isi)); err != nil {
			return dipotong, 0, fmt.Errorf("gagal memotong id %d: %w", p.ID, err)
		}
		dipotong++
	}

	for kiriman := 0; kiriman < maksKiriman; kiriman++ {
		daftar, err := s.repo.PotonganTanpaEmbedding(namaModel, ukuranKiriman)
		if err != nil || len(daftar) == 0 {
			return dipotong, divektor, err
		}
		// judul ikut dikirim agar potongan yang pendek tetap punya konteks
		daftarTeks := make([]string, len(daftar))
		for i, p := range daftar {
			daftarTeks[i] = p.Judul + "\n" + p.Isi
		}
		modelAgent, daftarVektor, err := s.agen.Embed(ctx, agen.EmbedDokumen, daftarTeks)
		if err != nil {
			return dipotong, divektor, err
		}
		if modelAgent != namaModel {
			return dipotong, divektor, fmt.Errorf("model embedding di agent berganti ke %q di tengah pengindeksan", modelAgent)
		}
		for i, p := range daftar {
			if err := s.repo.SimpanEmbedding(namaModel, p.ID, daftarVektor[i]); err != nil {
				return dipotong, divektor, fmt.Errorf("gagal menyimpan vektor potongan %d: %w", p.ID, err)
			}
			divektor++
		}
	}
	return dipotong, divektor, nil
}

// Sidik harus sama dengan md5(judul || E'\n' || isi) di Postgres
func Sidik(judul, isi string) string {
	jumlah := md5.Sum([]byte(judul + "\n" + isi))
	return hex.EncodeToString(jumlah[:])
}

// PecahPotongan membagi isi per paragraf, digabung sampai maksPotongan karakter;
// paragraf yang terlalu panjang dibagi per kalimat, dan kalimat yang terlalu panjang dipotong paksa
func PecahPotongan(isi string) []string {
	daftar := []string{}
	sekarang := ""
	tambah := func(bagian, pemisah string) {
		if sekarang != "" && utf8.RuneCountInString(sekarang)+len(pemisah)+utf8.RuneCountInString(bagian) > maksPotongan {
			daftar = append(daftar, sekarang)
			sekarang = ""
		}
		if sekarang == "" {
			sekarang = bagian
		} else {
			sekarang += pemisah + bagian
		}
	}

	for _, paragraf := range polaParagraf.Split(isi, -1) {
		paragraf = strings.TrimSpace(paragraf)
		if paragraf == "" {
			continue
		}
		if utf8.RuneCountInString(paragraf) <= maksPotongan {
			tambah(paragraf, "\n\n")
			continue
		}
		for _, kalimat := range pecahKalimat(paragraf) {
			for _, bagian := range potongPaksa(kalimat) {
				tambah(bagian, " ")
			}
		}
	}
	if sekarang != "" || len(daftar) == 0 {
		daftar = append(daftar, sekarang)
	}
	return daftar
}

// pecahKalimat memisah teks setelah tanda titik, tanya, atau seru, dan di setiap baris baru
func pecahKalimat(teks string) []string {
	daftar := []string{}
	for _, kalimat := range strings.Split(polaAkhirKalimat.ReplaceAllString(teks, "$1\x00"), "\x00") {
		if kalimat = strings.TrimSpace(kalimat); kalimat != "" {
			daftar = append(daftar, kalimat)
		}
	}
	return daftar
}

// potongPaksa memotong teks setiap maksPotongan karakter
func potongPaksa(teks string) []string {
	huruf := []rune(teks)
	daftar := []string{}
	for len(huruf) > maksPotongan {
		daftar = append(daftar, string(huruf[:maksPotongan]))
		huruf = huruf[maksPotongan:]
	}
	return append(daftar, string(huruf))
}
