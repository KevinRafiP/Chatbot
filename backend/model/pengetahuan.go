package model

import "time"

type Pengetahuan struct {
	ID         int       `json:"id"`
	Judul      string    `json:"judul"`
	Isi        string    `json:"isi"`
	KataKunci  string    `json:"kata_kunci"`
	DibuatPada time.Time `json:"dibuat_pada"`
}
