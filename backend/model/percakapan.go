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
	DiperbaruiPada time.Time `json:"diperbarui_pada"`
}

type Sumber struct {
	Judul string `json:"judul"`
	URL   string `json:"url"`
}

type Pesan struct {
	ID         string    `json:"id"`
	Pengirim   string    `json:"pengirim"`
	Isi        string    `json:"isi"`
	Sumber     []Sumber  `json:"sumber"`
	Favorit    bool      `json:"favorit"`
	DibuatPada time.Time `json:"dibuat_pada"`
}

// PesanFavorit adalah pesan berbintang beserta percakapan asalnya, untuk daftar pesan berbintang
type PesanFavorit struct {
	Pesan
	PercakapanID    string `json:"percakapan_id"`
	JudulPercakapan string `json:"judul_percakapan"`
}
