package model

import "time"

type Pengguna struct {
	ID    string `json:"id"`
	Nama  string `json:"nama"`
	Jenis string `json:"jenis"`
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
	DibuatPada time.Time `json:"dibuat_pada"`
}
