package model

import "time"

// Kinerja adalah catatan satu panggilan AI: berapa lama, berapa token, dan alat apa saja yang dipakai
type Kinerja struct {
	Profil         string    `json:"profil"`
	Berhasil       bool      `json:"berhasil"`
	Galat          string    `json:"galat,omitempty"`
	LamaMs         int64     `json:"lama_ms"`
	TokenMasuk     int       `json:"token_masuk"`
	TokenKeluar    int       `json:"token_keluar"`
	PanggilanLLM   int       `json:"panggilan_llm"`
	Alat           []string  `json:"alat"`
	PanjangJawaban int       `json:"panjang_jawaban"`
	DibuatPada     time.Time `json:"dibuat_pada"`
}

// StatistikKinerja adalah rangkuman banyak catatan kinerja; Profil kosong berarti semua profil
type StatistikKinerja struct {
	Profil      string `json:"profil"`
	Jumlah      int    `json:"jumlah"`
	Gagal       int    `json:"gagal"`
	RataLamaMs  int64  `json:"rata_lama_ms"`
	P90LamaMs   int64  `json:"p90_lama_ms"`
	RataToken   int64  `json:"rata_token"`
	TokenMasuk  int64  `json:"token_masuk"`
	TokenKeluar int64  `json:"token_keluar"`
}

// PemakaianAlat adalah berapa kali satu alat agent dipakai
type PemakaianAlat struct {
	Nama   string `json:"nama"`
	Jumlah int    `json:"jumlah"`
}

// LaporanKinerja adalah isi halaman kinerja admin untuk beberapa hari terakhir
type LaporanKinerja struct {
	Hari      int                `json:"hari"`
	Semua     StatistikKinerja   `json:"semua"` // semua jawaban, tanpa peringkasan percakapan
	PerProfil []StatistikKinerja `json:"per_profil"`
	Alat      []PemakaianAlat    `json:"alat"`
	Terbaru   []Kinerja          `json:"terbaru"`
}
