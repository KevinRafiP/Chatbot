package model

import "time"

type Pengguna struct {
	ID            string `json:"id"`
	Nama          string `json:"nama"`
	Jenis         string `json:"jenis"`
	Email         string `json:"email,omitempty"`
	Terverifikasi bool   `json:"-"` // Terverifikasi hanya dipakai di backend, tidak dikirim ke browser
}

type Percakapan struct {
	ID             string    `json:"id"`
	Judul          string    `json:"judul"`
	Disematkan     bool      `json:"disematkan"`
	DiperbaruiPada time.Time `json:"diperbarui_pada"`
	Menjawab       bool      `json:"menjawab,omitempty"` // true selama jawaban percakapan ini masih dibuat
	Gagal          bool      `json:"gagal,omitempty"`    // true bila jawaban terakhir gagal dan belum dicoba lagi
}

type Sumber struct {
	Judul string `json:"judul"`
	URL   string `json:"url"`
}

type Pesan struct {
	ID         string    `json:"id"`
	Urutan     int64     `json:"-"`
	Pengirim   string    `json:"pengirim"`
	Isi        string    `json:"isi"`
	Sumber     []Sumber  `json:"sumber"`
	Favorit    bool      `json:"favorit"`
	Penilaian  int       `json:"penilaian"` // 1 suka, -1 tidak suka, 0 belum dinilai
	Lampiran   string    `json:"lampiran,omitempty"`
	DibuatPada time.Time `json:"dibuat_pada"`
}

// Lampiran adalah berkas yang diunggah bersama pesan; Teks hanya disimpan di backend, browser cukup melihat namanya
type Lampiran struct {
	Nama string `json:"nama"`
	Teks string `json:"teks"`
}

// HasilCari adalah percakapan yang cocok dengan pencarian, dengan potongan pesan tempat kata itu ditemukan
type HasilCari struct {
	Percakapan
	Cuplikan string `json:"cuplikan"`
}

// PesanFavorit adalah pesan berbintang beserta percakapan asalnya, untuk daftar pesan berbintang
type PesanFavorit struct {
	Pesan
	PercakapanID    string `json:"percakapan_id"`
	JudulPercakapan string `json:"judul_percakapan"`
}
