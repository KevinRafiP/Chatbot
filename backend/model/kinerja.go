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
	PenggunaID     string    `json:"-"`
	JenisAkun      string    `json:"-"`
	Akun           string    `json:"akun"`      // kunci akun, lihat KinerjaAkun
	NamaAkun       string    `json:"nama_akun"` // kosong untuk tamu dan catatan tanpa akun
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

// PenilaianJawaban adalah jumlah suka dan tidak suka dari pengguna; Profil kosong berarti semua profil
type PenilaianJawaban struct {
	Profil    string `json:"profil"`
	Suka      int    `json:"suka"`
	TidakSuka int    `json:"tidak_suka"`
}

// JawabanDinilai adalah potongan jawaban yang tidak disukai beserta pertanyaannya
type JawabanDinilai struct {
	Profil      string    `json:"profil"`
	Pertanyaan  string    `json:"pertanyaan"`
	Jawaban     string    `json:"jawaban"`
	DinilaiPada time.Time `json:"dinilai_pada"`
}

// LaporanKinerja adalah isi halaman kinerja admin untuk satu rentang waktu
type LaporanKinerja struct {
	Hari         int                `json:"hari"` // 0 berarti rentang tanggal pilihan sendiri
	Dari         time.Time          `json:"dari"`
	Sampai       time.Time          `json:"sampai"`
	Semua        StatistikKinerja   `json:"semua"` // semua jawaban, tanpa peringkasan percakapan
	PerProfil    []StatistikKinerja `json:"per_profil"`
	Alat         []PemakaianAlat    `json:"alat"`
	PerAkun      []KinerjaAkun      `json:"per_akun"`      // selalu semua akun, walau laporan disaring satu akun
	Akun         string             `json:"akun"`          // akun yang sedang disaring; kosong = semua akun
	Penilaian    []PenilaianJawaban `json:"penilaian"`     // baris pertama adalah total
	TidakDisukai []JawabanDinilai   `json:"tidak_disukai"` // kosong bila KINERJA_TAMPILKAN_ISI=tidak
}

// HalamanKinerja adalah satu halaman tabel "Terbaru"; Total adalah jumlah semua catatan di rentang waktu
type HalamanKinerja struct {
	Baris      []Kinerja `json:"baris"`
	Total      int       `json:"total"`
	Halaman    int       `json:"halaman"`
	PerHalaman int       `json:"per_halaman"`
}

// KinerjaAkun adalah rangkuman jawaban untuk satu akun. Akun berisi id akun terdaftar, "tamu" untuk semua tamu,
// atau "lain" untuk catatan sebelum fitur ini dan akun yang sudah dihapus
type KinerjaAkun struct {
	Akun        string    `json:"akun"`
	Nama        string    `json:"nama"`
	Email       string    `json:"email,omitempty"`
	Jenis       string    `json:"jenis"`
	Jumlah      int       `json:"jumlah"`
	Gagal       int       `json:"gagal"`
	RataLamaMs  int64     `json:"rata_lama_ms"`
	TokenMasuk  int64     `json:"token_masuk"`
	TokenKeluar int64     `json:"token_keluar"`
	Terakhir    time.Time `json:"terakhir"`
}
