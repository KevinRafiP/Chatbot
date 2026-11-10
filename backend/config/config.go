package config

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	AppPort             string
	CORSOrigin          []string
	DatabaseURL         string
	DBHost              string
	DBPort              string
	DBUser              string
	DBPassword          string
	DBName              string
	DBSSLMode           string
	AgentURL            string
	AgentAPIKey         string
	AgentStreamMenit    int
	SesiHari            int
	BatasTamuPerJam     int
	BatasPesanPerMenit  int
	IngestionPort       string
	IngestionAPIKey     string
	WorkerIntervalMenit int
	EksporFolder        string
	EksporURL           string
	EksporKunci         string
	EksporDriveFolder   string
	SesiTamuJam         int
	BatasAkunPerMenit   int
	BatasPesanGlobal    int
	BatasPesanTamu      int
	EmailAdmin          []string
	EmailLayanan        string
	EmailAPIKey         string
	EmailPengirim       string
	NamaPengirim        string
	FrontendURL         string
	BerkasMaksMB        int
	BatasBerkasPerJam   int
	EmailJawabanPerHari int
	KinerjaSimpanHari   int
	KinerjaTampilkanIsi bool
	KinerjaPerHalaman   int
	KinerjaBarisAlat    int
	RingkasanSetelah    int
	RingkasanSisa       int
	TurnstileRahasia    string
	TurnstileURL        string
	BatasGagalMasuk     int
	JedaGagalMenit      int
	TokenHarianAkun     int
	TokenHarianSemua    int
}

func Muat() Config {
	godotenv.Load()

	return Config{
		AppPort:             ambil("APP_PORT", ambil("PORT", "8080")),
		CORSOrigin:          ambilDaftar("CORS_ORIGIN", "http://localhost:5173"),
		DatabaseURL:         ambil("DATABASE_URL", ""),
		DBHost:              ambil("DB_HOST", "localhost"),
		DBPort:              ambil("DB_PORT", "5432"),
		DBUser:              ambil("DB_USER", "postgres"),
		DBPassword:          ambil("DB_PASSWORD", ""),
		DBName:              ambil("DB_NAME", "latihan_chatbot"),
		DBSSLMode:           ambil("DB_SSLMODE", "disable"),
		AgentURL:            ambil("AGENT_URL", ""),
		AgentAPIKey:         ambil("AGENT_API_KEY", ""),
		AgentStreamMenit:    ambilAngka("AGENT_BATAS_STREAM_MENIT", 5),
		IngestionPort:       ambil("INGESTION_PORT", "8081"),
		IngestionAPIKey:     ambil("INGESTION_API_KEY", ""),
		WorkerIntervalMenit: ambilAngka("WORKER_INTERVAL_MENIT", 1),
		EksporFolder:        ambil("EKSPOR_FOLDER", "ekspor"),
		EksporURL:           ambil("EKSPOR_URL", ""),
		EksporKunci:         ambil("EKSPOR_KUNCI", ""),
		EksporDriveFolder:   ambil("EKSPOR_DRIVE_FOLDER", ""),
		SesiHari:            ambilAngka("SESI_HARI", 30),
		BatasTamuPerJam:     ambilAngka("BATAS_TAMU_PER_JAM", 10),
		BatasPesanPerMenit:  ambilAngka("BATAS_PESAN_PER_MENIT", 20),
		SesiTamuJam:         ambilAngka("SESI_TAMU_JAM", 10),
		BatasAkunPerMenit:   ambilAngka("BATAS_AKUN_PER_MENIT", 10),
		BatasPesanGlobal:    ambilAngka("BATAS_PESAN_GLOBAL_PER_MENIT", 60),
		BatasPesanTamu:      ambilAngka("BATAS_PESAN_TAMU", 5),
		EmailAdmin:          ambilDaftar("ADMIN_EMAIL", ""),
		EmailLayanan:        ambil("EMAIL_LAYANAN", ""),
		EmailAPIKey:         ambil("EMAIL_API_KEY", ""),
		EmailPengirim:       ambil("EMAIL_PENGIRIM", ""),
		NamaPengirim:        ambil("NAMA_PENGIRIM", "Vokapas"),
		FrontendURL:         ambil("FRONTEND_URL", ""),
		BerkasMaksMB:        ambilAngkaBolehNol("BERKAS_MAKS_MB", 5),
		BatasBerkasPerJam:   ambilAngka("BATAS_BERKAS_PER_JAM", 20),
		EmailJawabanPerHari: ambilAngkaBolehNol("EMAIL_JAWABAN_PER_HARI", 5),
		KinerjaSimpanHari:   ambilAngkaBolehNol("KINERJA_SIMPAN_HARI", 30),
		KinerjaTampilkanIsi: ambil("KINERJA_TAMPILKAN_ISI", "ya") != "tidak",
		KinerjaPerHalaman:   ambilAngka("KINERJA_BARIS_PER_HALAMAN", 20),
		KinerjaBarisAlat:    ambilAngka("KINERJA_BARIS_ALAT", 15),
		RingkasanSetelah:    ambilAngkaBolehNol("RINGKASAN_SETELAH_PESAN", 20),
		RingkasanSisa:       ambilAngkaBolehNol("RINGKASAN_SISA_PESAN", 10),
		TurnstileRahasia:    ambil("TURNSTILE_SECRET", ""),
		TurnstileURL:        ambil("TURNSTILE_URL", ""),
		BatasGagalMasuk:     ambilAngkaBolehNol("BATAS_GAGAL_MASUK", 5),
		JedaGagalMenit:      ambilAngka("JEDA_GAGAL_MASUK_MENIT", 15),
		TokenHarianAkun:     ambilAngkaBolehNol("BATAS_TOKEN_HARIAN_AKUN", 1000000),
		TokenHarianSemua:    ambilAngkaBolehNol("BATAS_TOKEN_HARIAN_SEMUA", 0),
	}
}

// DSN mengembalikan alamat database: DATABASE_URL bila diisi, selain itu dirakit dari bagian DB_*
func (c Config) DSN() string {
	if c.DatabaseURL != "" {
		return c.DatabaseURL
	}
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		c.DBHost, c.DBPort, c.DBUser, c.DBPassword, c.DBName, c.DBSSLMode)
}

// AlamatDatabase menampilkan host dan nama database tanpa kata sandi, untuk tabel saat menyala
func (c Config) AlamatDatabase() string {
	if c.DatabaseURL == "" {
		return fmt.Sprintf("%s:%s/%s", c.DBHost, c.DBPort, c.DBName)
	}
	alamat, err := url.Parse(c.DatabaseURL)
	if err != nil {
		return "DATABASE_URL"
	}
	return alamat.Host + alamat.Path
}

func ambil(kunci, bawaan string) string {
	if nilai := os.Getenv(kunci); nilai != "" {
		return nilai
	}
	return bawaan
}

func ambilAngka(kunci string, bawaan int) int {
	nilai, err := strconv.Atoi(os.Getenv(kunci))
	if err != nil || nilai <= 0 {
		return bawaan
	}
	return nilai
}

// ambilAngkaBolehNol sama seperti ambilAngka, tetapi 0 dipakai apa adanya untuk mematikan fitur
func ambilAngkaBolehNol(kunci string, bawaan int) int {
	nilai, err := strconv.Atoi(os.Getenv(kunci))
	if err != nil || nilai < 0 {
		return bawaan
	}
	return nilai
}

// ambilDaftar membaca nilai yang dipisah koma menjadi daftar, contoh "a,b" menjadi ["a", "b"]
func ambilDaftar(kunci, bawaan string) []string {
	daftar := []string{}
	for _, bagian := range strings.Split(ambil(kunci, bawaan), ",") {
		if bagian = strings.TrimSpace(bagian); bagian != "" {
			daftar = append(daftar, strings.TrimRight(bagian, "/"))
		}
	}
	return daftar
}
