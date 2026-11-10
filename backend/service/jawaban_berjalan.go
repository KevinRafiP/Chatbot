package service

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	"chatbot/backend/agen"
)

const (
	// BatasJawabanPerAkun adalah jumlah jawaban yang boleh dibuat bersamaan oleh satu akun di percakapan berbeda
	BatasJawabanPerAkun = 3
	// BatasWaktuJawaban menghentikan jawaban yang macet, karena jawaban tidak lagi berhenti saat browser ditutup
	BatasWaktuJawaban = 30 * time.Minute
	// SimpanGagal adalah lama jawaban gagal tetap diingat, agar pengguna yang kembali ke percakapannya
	// melihat pertanyaan itu dengan tanda gagal dan tombol "Coba lagi"
	SimpanGagal = time.Hour
)

var (
	ErrSedangMenjawab       = errors.New("percakapan ini masih membuat jawaban, tunggu sampai selesai atau hentikan dulu")
	ErrTerlaluBanyakJawaban = fmt.Errorf("paling banyak %d jawaban dibuat bersamaan, tunggu salah satunya selesai", BatasJawabanPerAkun)
	ErrTidakMenjawab        = errors.New("tidak ada jawaban yang sedang dibuat di percakapan ini")
)

// Peristiwa adalah satu kabar dari agent (status, teks, ulang, jalankan_kode) yang disimpan agar bisa diputar ulang
type Peristiwa struct {
	Jenis string
	Data  json.RawMessage
}

// InfoJawaban menjelaskan pertanyaan yang sedang dijawab, untuk browser yang menyambung setelah refresh
type InfoJawaban struct {
	Pertanyaan  string    `json:"pertanyaan"`
	Lampiran    string    `json:"lampiran,omitempty"`
	Mode        string    `json:"mode"`
	DimulaiPada time.Time `json:"dimulai_pada"`
}

// JawabanBerjalan adalah jawaban yang dibuat di server tanpa bergantung pada koneksi browser;
// browser bisa pergi lalu menyambung lagi dan menerima semua kabar dari awal
type JawabanBerjalan struct {
	Info       InfoJawaban
	penggunaID string
	batal      context.CancelFunc
	// permintaan disimpan agar jawaban bisa dibuat ulang dengan arahan tambahan dari pengguna
	permintaan PermintaanJawab
	// gagalPada diisi saat jawaban gagal (bukan dihentikan pengguna); dibaca dan diubah di bawah kunci pengelola
	gagalPada time.Time

	kunci     sync.Mutex
	peristiwa []Peristiwa
	selesai   bool
	hasil     HasilPesan
	err       error
	baru      chan struct{}
}

// tambah menyimpan satu kabar lalu membangunkan semua browser yang sedang menunggu
func (j *JawabanBerjalan) tambah(jenis string, data json.RawMessage) {
	j.kunci.Lock()
	defer j.kunci.Unlock()
	j.peristiwa = append(j.peristiwa, Peristiwa{Jenis: jenis, Data: append(json.RawMessage(nil), data...)})
	close(j.baru)
	j.baru = make(chan struct{})
}

func (j *JawabanBerjalan) akhiri(hasil HasilPesan, err error) {
	j.kunci.Lock()
	defer j.kunci.Unlock()
	j.selesai, j.hasil, j.err = true, hasil, err
	close(j.baru)
	j.baru = make(chan struct{})
}

// Keadaan adalah potret jawaban: kabar yang belum dibaca, hasil akhir jika sudah selesai,
// dan Baru yang ditutup saat ada kabar berikutnya
type Keadaan struct {
	Peristiwa []Peristiwa
	Selesai   bool
	Hasil     HasilPesan
	Err       error
	Baru      <-chan struct{}
}

// Ambil mengembalikan kabar mulai urutan ke-dari beserta keadaan jawaban saat ini
func (j *JawabanBerjalan) Ambil(dari int) Keadaan {
	j.kunci.Lock()
	defer j.kunci.Unlock()
	k := Keadaan{Selesai: j.selesai, Hasil: j.hasil, Err: j.err, Baru: j.baru}
	if dari < len(j.peristiwa) {
		k.Peristiwa = append(k.Peristiwa, j.peristiwa[dari:]...)
	}
	return k
}

// Tunggu menunggu jawaban selesai, untuk permintaan yang tidak memakai stream
func (j *JawabanBerjalan) Tunggu(ctx context.Context) (HasilPesan, error) {
	for {
		k := j.Ambil(1 << 30)
		if k.Selesai {
			return k.Hasil, k.Err
		}
		select {
		case <-ctx.Done():
			return HasilPesan{}, ctx.Err()
		case <-k.Baru:
		}
	}
}

// pengelolaJawaban mencatat jawaban yang sedang dibuat, paling banyak satu untuk setiap percakapan,
// dan jawaban yang gagal selama SimpanGagal sampai pertanyaan berikutnya dikirim
type pengelolaJawaban struct {
	kunci    sync.Mutex
	berjalan map[string]*JawabanBerjalan
}

func baruPengelolaJawaban() *pengelolaJawaban {
	return &pengelolaJawaban{berjalan: map[string]*JawabanBerjalan{}}
}

// mulai menjalankan kerja di latar belakang; ErrSedangMenjawab jika percakapan ini masih menjawab.
// siapkan dijalankan setelah semua pemeriksaan lolos dan sebelum kerja dimulai, jadi pesan lama hanya
// disembunyikan bila jawaban barunya memang dibuat; hasilnya info pertanyaan dan permintaan untuk dibuat ulang
func (p *pengelolaJawaban) mulai(percakapanID, penggunaID string, siapkan func() (InfoJawaban, PermintaanJawab, error),
	kerja func(context.Context, agen.Kabar) (HasilPesan, error)) (*JawabanBerjalan, error) {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	p.buangKedaluwarsa()
	if j, ada := p.berjalan[percakapanID]; ada && j.gagalPada.IsZero() {
		return nil, ErrSedangMenjawab
	}
	jumlah := 0
	for _, j := range p.berjalan {
		if j.penggunaID == penggunaID && j.gagalPada.IsZero() {
			jumlah++
		}
	}
	if jumlah >= BatasJawabanPerAkun {
		return nil, ErrTerlaluBanyakJawaban
	}
	info, permintaan, err := siapkan()
	if err != nil {
		return nil, err
	}

	ctx, batal := context.WithTimeout(context.Background(), BatasWaktuJawaban)
	j := &JawabanBerjalan{Info: info, penggunaID: penggunaID, batal: batal, permintaan: permintaan, baru: make(chan struct{})}
	p.berjalan[percakapanID] = j
	go p.jalankan(ctx, percakapanID, j, kerja)
	return j, nil
}

func (p *pengelolaJawaban) jalankan(ctx context.Context, percakapanID string, j *JawabanBerjalan, kerja func(context.Context, agen.Kabar) (HasilPesan, error)) {
	var hasil HasilPesan
	var err error
	defer func() {
		// panic di latar belakang tidak ditangkap net/http, jadi ditangkap di sini agar server tidak mati
		if r := recover(); r != nil {
			log.Println("panic saat membuat jawaban:", r)
			err = fmt.Errorf("panic: %v", r)
		}
		j.batal()
		// yang berhasil sudah tersimpan dan yang dihentikan memang diminta pengguna, jadi keduanya dihapus dulu baru diakhiri;
		// yang gagal tetap diingat agar terlihat saat pengguna kembali
		p.kunci.Lock()
		if err != nil && !errors.Is(err, context.Canceled) {
			j.gagalPada = time.Now()
		} else {
			delete(p.berjalan, percakapanID)
		}
		p.kunci.Unlock()
		j.akhiri(hasil, err)
	}()
	hasil, err = kerja(ctx, j.tambah)
}

// buangKedaluwarsa melupakan jawaban gagal yang sudah lebih lama dari SimpanGagal; dipanggil di bawah kunci
func (p *pengelolaJawaban) buangKedaluwarsa() {
	for id, j := range p.berjalan {
		if !j.gagalPada.IsZero() && time.Since(j.gagalPada) > SimpanGagal {
			delete(p.berjalan, id)
		}
	}
}

// ambil mengembalikan jawaban yang sedang dibuat atau baru gagal di percakapan milik pengguna, atau nil
func (p *pengelolaJawaban) ambil(percakapanID, penggunaID string) *JawabanBerjalan {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	p.buangKedaluwarsa()
	if j, ada := p.berjalan[percakapanID]; ada && j.penggunaID == penggunaID {
		return j
	}
	return nil
}

// sedangMenjawab mengembalikan jawaban yang masih dibuat (bukan yang sudah gagal) di percakapan milik pengguna, atau nil
func (p *pengelolaJawaban) sedangMenjawab(percakapanID, penggunaID string) *JawabanBerjalan {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	if j, ada := p.berjalan[percakapanID]; ada && j.penggunaID == penggunaID && j.gagalPada.IsZero() {
		return j
	}
	return nil
}

// hentikan membatalkan jawaban yang sedang dibuat dan melupakan jawaban gagal; false jika tidak ada yang berjalan
func (p *pengelolaJawaban) hentikan(percakapanID, penggunaID string) bool {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	j, ada := p.berjalan[percakapanID]
	if !ada || j.penggunaID != penggunaID {
		return false
	}
	if !j.gagalPada.IsZero() {
		delete(p.berjalan, percakapanID)
		return false
	}
	j.batal()
	return true
}

// keadaan mengembalikan id percakapan milik pengguna yang sedang dibuatkan jawaban dan yang jawabannya baru gagal
func (p *pengelolaJawaban) keadaan(penggunaID string) (menjawab, gagal map[string]bool) {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	p.buangKedaluwarsa()
	menjawab, gagal = map[string]bool{}, map[string]bool{}
	for id, j := range p.berjalan {
		if j.penggunaID != penggunaID {
			continue
		}
		if j.gagalPada.IsZero() {
			menjawab[id] = true
		} else {
			gagal[id] = true
		}
	}
	return menjawab, gagal
}
