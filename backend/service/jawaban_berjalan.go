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
)

var (
	ErrSedangMenjawab       = errors.New("percakapan ini masih membuat jawaban, tunggu sampai selesai atau hentikan dulu")
	ErrTerlaluBanyakJawaban = fmt.Errorf("paling banyak %d jawaban dibuat bersamaan, tunggu salah satunya selesai", BatasJawabanPerAkun)
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

// pengelolaJawaban mencatat jawaban yang sedang dibuat, paling banyak satu untuk setiap percakapan
type pengelolaJawaban struct {
	kunci    sync.Mutex
	berjalan map[string]*JawabanBerjalan
}

func baruPengelolaJawaban() *pengelolaJawaban {
	return &pengelolaJawaban{berjalan: map[string]*JawabanBerjalan{}}
}

// mulai menjalankan kerja di latar belakang; ErrSedangMenjawab jika percakapan ini masih menjawab
func (p *pengelolaJawaban) mulai(percakapanID, penggunaID string, info InfoJawaban, kerja func(context.Context, agen.Kabar) (HasilPesan, error)) (*JawabanBerjalan, error) {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	if _, ada := p.berjalan[percakapanID]; ada {
		return nil, ErrSedangMenjawab
	}
	jumlah := 0
	for _, j := range p.berjalan {
		if j.penggunaID == penggunaID {
			jumlah++
		}
	}
	if jumlah >= BatasJawabanPerAkun {
		return nil, ErrTerlaluBanyakJawaban
	}

	ctx, batal := context.WithTimeout(context.Background(), BatasWaktuJawaban)
	j := &JawabanBerjalan{Info: info, penggunaID: penggunaID, batal: batal, baru: make(chan struct{})}
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
		// dihapus dulu baru diakhiri: jawaban sudah tersimpan, jadi browser yang datang sesudahnya cukup memuat pesan
		p.kunci.Lock()
		delete(p.berjalan, percakapanID)
		p.kunci.Unlock()
		j.akhiri(hasil, err)
	}()
	hasil, err = kerja(ctx, j.tambah)
}

// ambil mengembalikan jawaban yang sedang dibuat di percakapan milik pengguna, atau nil
func (p *pengelolaJawaban) ambil(percakapanID, penggunaID string) *JawabanBerjalan {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	if j, ada := p.berjalan[percakapanID]; ada && j.penggunaID == penggunaID {
		return j
	}
	return nil
}

// hentikan membatalkan jawaban yang sedang dibuat; false jika tidak ada
func (p *pengelolaJawaban) hentikan(percakapanID, penggunaID string) bool {
	j := p.ambil(percakapanID, penggunaID)
	if j == nil {
		return false
	}
	j.batal()
	return true
}

// menjawab mengembalikan id percakapan milik pengguna yang sedang dibuatkan jawaban
func (p *pengelolaJawaban) menjawab(penggunaID string) map[string]bool {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	daftar := map[string]bool{}
	for id, j := range p.berjalan {
		if j.penggunaID == penggunaID {
			daftar[id] = true
		}
	}
	return daftar
}
