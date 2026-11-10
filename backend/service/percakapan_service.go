package service

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const (
	BatasRiwayat     = 20
	BatasPertanyaan  = 2000
	BatasJudul       = 40
	BatasJudulManual = 100
	BatasCari        = 30
	BatasKueriCari   = 100
	// TungguBerhenti adalah lama menunggu jawaban lama berhenti sebelum dibuat ulang dengan arahan tambahan
	TungguBerhenti = 15 * time.Second
)

var (
	ErrPercakapanTidakAda = errors.New("percakapan tidak ditemukan")
	ErrJudulTidakValid    = errors.New("judul tidak valid")
	ErrPesanTidakAda      = errors.New("pesan tidak ditemukan")
	ErrPenilaianSalah     = errors.New("penilaian harus 1, -1, atau 0")
	BatasFavorit          = 200
)

type HasilPesan struct {
	Judul   string      `json:"judul"`
	Pesan   model.Pesan `json:"pesan"`
	Jawaban model.Pesan `json:"jawaban"`
	// Saran adalah pertanyaan lanjutan usulan AI; tidak disimpan, hanya tampil di bawah jawaban terbaru
	Saran []string `json:"saran,omitempty"`
}

// PermintaanJawab adalah pertanyaan yang akan dijawab. GantiDari boleh kosong; jika diisi id pertanyaan lama,
// pertanyaan itu dan semua pesan sesudahnya disembunyikan lalu diganti, untuk edit pertanyaan dan buat ulang jawaban
type PermintaanJawab struct {
	Pertanyaan string
	Mode       string
	Lampiran   *model.Lampiran
	GantiDari  string
}

type PercakapanService struct {
	repo      *repository.PercakapanRepository
	chatbot   *ChatbotService
	ingatan   *IngatanService
	email     *EmailJawabanService
	ringkasan *RingkasanService
	berjalan  *pengelolaJawaban
}

// email boleh nil; jawaban lalu tidak bisa dikirim ke email. ringkasan boleh nil; pesan lama lalu tidak diringkas
func BaruPercakapanService(repo *repository.PercakapanRepository, chatbot *ChatbotService, ingatan *IngatanService, email *EmailJawabanService, ringkasan *RingkasanService) *PercakapanService {
	return &PercakapanService{repo: repo, chatbot: chatbot, ingatan: ingatan, email: email, ringkasan: ringkasan,
		berjalan: baruPengelolaJawaban()}
}

// Daftar mengambil percakapan pengguna dan menandai yang sedang dibuatkan jawaban atau jawabannya baru gagal
func (s *PercakapanService) Daftar(penggunaID string) ([]model.Percakapan, error) {
	daftar, err := s.repo.Semua(penggunaID)
	if err != nil {
		return nil, err
	}
	menjawab, gagal := s.berjalan.keadaan(penggunaID)
	for i := range daftar {
		daftar[i].Menjawab = menjawab[daftar[i].ID]
		daftar[i].Gagal = gagal[daftar[i].ID]
	}
	return daftar, nil
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
	s.berjalan.hentikan(id, penggunaID)
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

// Mulai memeriksa pertanyaan lalu membuat jawabannya di latar belakang, jadi jawaban tetap dibuat
// walau browser di-refresh, pindah percakapan, atau ditutup. Satu percakapan hanya boleh punya satu jawaban berjalan
func (s *PercakapanService) Mulai(id string, pengguna model.Pengguna, p PermintaanJawab) (*JawabanBerjalan, error) {
	p.Pertanyaan = strings.TrimSpace(p.Pertanyaan)
	if p.Pertanyaan == "" || len(p.Pertanyaan) > BatasPertanyaan {
		return nil, ErrDataTidakValid
	}
	if err := s.pastikanMilik(id, pengguna.ID); err != nil {
		return nil, err
	}
	p.Lampiran = bersihkanLampiran(p.Lampiran)

	siapkan := func() (InfoJawaban, PermintaanJawab, error) {
		if p.GantiDari != "" {
			lama, err := s.repo.HapusPesanMulai(id, p.GantiDari)
			if errors.Is(err, sql.ErrNoRows) {
				return InfoJawaban{}, p, ErrPesanTidakAda
			}
			if err != nil {
				return InfoJawaban{}, p, err
			}
			// berkas pertanyaan lama ikut lagi ke penggantinya bila pengguna tidak mengunggah berkas baru
			if p.Lampiran == nil && lama.Nama != "" {
				p.Lampiran = &lama
			}
			p.GantiDari = ""
		}
		info := InfoJawaban{Pertanyaan: p.Pertanyaan, Mode: profilPengguna(p.Mode), DimulaiPada: time.Now()}
		if p.Lampiran != nil {
			info.Lampiran = p.Lampiran.Nama
		}
		return info, p, nil
	}
	return s.berjalan.mulai(id, pengguna.ID, siapkan, func(ctx context.Context, kabar agen.Kabar) (HasilPesan, error) {
		return s.Kirim(ctx, id, pengguna, p.Pertanyaan, p.Mode, p.Lampiran, kabar)
	})
}

// Arahkan menghentikan jawaban yang sedang dibuat lalu membuatnya ulang dari awal dengan arahan tambahan pengguna,
// misalnya "pakai bahasa Go saja" yang diketik saat AI masih berpikir. Jika jawaban lama keburu selesai,
// tanya jawab itu diganti, jadi percakapan tetap berisi satu pertanyaan dengan arahannya
func (s *PercakapanService) Arahkan(id string, pengguna model.Pengguna, tambahan string) (*JawabanBerjalan, error) {
	tambahan = strings.TrimSpace(tambahan)
	j := s.berjalan.sedangMenjawab(id, pengguna.ID)
	if j == nil {
		return nil, ErrTidakMenjawab
	}
	p := j.permintaan
	p.Pertanyaan = strings.TrimSpace(p.Pertanyaan + "\n\nTambahan: " + tambahan)
	if tambahan == "" || len(p.Pertanyaan) > BatasPertanyaan {
		return nil, ErrDataTidakValid
	}

	s.berjalan.hentikan(id, pengguna.ID)
	ctx, batal := context.WithTimeout(context.Background(), TungguBerhenti)
	defer batal()
	hasil, err := j.Tunggu(ctx)
	if !j.Ambil(1 << 30).Selesai {
		return nil, ErrSedangMenjawab
	}
	if err == nil {
		p.GantiDari = hasil.Pesan.ID
	}
	return s.Mulai(id, pengguna, p)
}

// Cari mencari percakapan pengguna dari judul atau isi pesannya
func (s *PercakapanService) Cari(penggunaID, kueri string) ([]model.HasilCari, error) {
	kueri = strings.TrimSpace(kueri)
	if kueri == "" {
		return []model.HasilCari{}, nil
	}
	if huruf := []rune(kueri); len(huruf) > BatasKueriCari {
		kueri = string(huruf[:BatasKueriCari])
	}
	return s.repo.Cari(penggunaID, kueri, BatasCari)
}

// JawabanBerjalan mengembalikan jawaban yang sedang dibuat atau baru gagal di percakapan milik pengguna, atau nil
func (s *PercakapanService) JawabanBerjalan(id, penggunaID string) *JawabanBerjalan {
	return s.berjalan.ambil(id, penggunaID)
}

// Hentikan membatalkan jawaban yang sedang dibuat; false jika tidak ada yang berjalan
func (s *PercakapanService) Hentikan(id, penggunaID string) bool {
	return s.berjalan.hentikan(id, penggunaID)
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

	// pesan yang sudah diringkas tidak dikirim utuh lagi; ringkasannya ikut dikirim ke agent
	ringkasan, sampai := s.ringkasan.Ambil(id)
	lama, err := s.repo.DaftarPesanSetelah(id, sampai, BatasRiwayat)
	if err != nil {
		return HasilPesan{}, err
	}
	riwayat := []agen.Riwayat{}
	for _, p := range lama {
		riwayat = append(riwayat, agen.Riwayat{Peran: p.Pengirim, Teks: p.Isi + teksSumber(p.Sumber)})
	}

	// judul dipasang sebelum menjawab, agar percakapan yang jawabannya gagal saat ditinggal tetap bisa dikenali di daftar
	judul := ""
	if sampai == 0 && len(lama) == 0 {
		judul = potong(pertanyaan, BatasJudul)
		if err := s.repo.UbahJudul(id, judul); err != nil {
			return HasilPesan{}, err
		}
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

	ingatan, waktunya := s.ingatan.Ambil(penggunaID)
	tambahan := agen.Tambahan{Lampiran: lampiranAgen(&berkas), BisaEmail: s.email.Bisa(pengguna), Ringkasan: ringkasan}
	profil := profilPengguna(mode)
	hasil, err := s.chatbot.Jawab(ctx, pengguna, pertanyaan, riwayat, ingatan, profil, tambahan, kabar)
	if err != nil {
		return HasilPesan{}, err
	}
	if hasil.Email != nil && tambahan.BisaEmail {
		if err := s.email.Kirim(pengguna, hasil.Email); err != nil {
			log.Println("gagal mengirim jawaban ke email:", err)
			hasil.Jawaban += "\n\n*Email belum terkirim: " + alasanEmail(err) + ".*"
		}
	}
	// pertanyaan baru disimpan bersama jawabannya; yang gagal atau dihentikan tidak tersimpan dan bisa dicoba lagi
	pesan, jawaban, err := s.repo.SimpanTanyaJawab(id, pertanyaan, baru, hasil.Jawaban, hasil.Sumber, profil)
	if err != nil {
		return HasilPesan{}, err
	}

	if waktunya {
		terbaru := append(riwayat, agen.Riwayat{Peran: "user", Teks: pertanyaan}, agen.Riwayat{Peran: "asisten", Teks: hasil.Jawaban})
		s.ingatan.PerbaruiNanti(penggunaID, ingatan, terbaru)
	}
	s.ringkasan.PerbaruiNanti(id, pengguna, len(lama)+2)
	return HasilPesan{Judul: judul, Pesan: pesan, Jawaban: jawaban, Saran: hasil.Saran}, nil
}

// Sematkan menaruh percakapan di atas daftar, atau melepasnya
func (s *PercakapanService) Sematkan(id, penggunaID string, sematkan bool) error {
	berubah, err := s.repo.Sematkan(id, penggunaID, sematkan)
	if err != nil {
		return err
	}
	if !berubah {
		return ErrPercakapanTidakAda
	}
	return nil
}

// Nilai menyimpan suka (1), tidak suka (-1), atau menghapus penilaian (0) pada jawaban asisten milik pengguna
func (s *PercakapanService) Nilai(pesanID, penggunaID string, nilai int) error {
	if nilai < -1 || nilai > 1 {
		return ErrPenilaianSalah
	}
	berubah, err := s.repo.UbahPenilaian(pesanID, penggunaID, nilai)
	if err != nil {
		return err
	}
	if !berubah {
		return ErrPesanTidakAda
	}
	return nil
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
