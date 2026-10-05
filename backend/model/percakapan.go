package model

import "time"

type Pengguna struct {
	ID    int64  `json:"id"`
	Nama  string `json:"nama"`
	Jenis string `json:"jenis"`
}

type Percakapan struct {
	ID             int64     `json:"id"`
	Judul          string    `json:"judul"`
	DiperbaruiPada time.Time `json:"diperbarui_pada"`
}

type Pesan struct {
	ID         int64     `json:"id"`
	Pengirim   string    `json:"pengirim"`
	Isi        string    `json:"isi"`
	Sumber     []string  `json:"sumber"`
	DibuatPada time.Time `json:"dibuat_pada"`
}
