package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	AppPort             string
	CORSOrigin          []string
	DBHost              string
	DBPort              string
	DBUser              string
	DBPassword          string
	DBName              string
	DBSSLMode           string
	AgentURL            string
	AgentAPIKey         string
	SesiHari            int
	BatasTamuPerJam     int
	BatasPesanPerMenit  int
	IngestionPort       string
	IngestionAPIKey     string
	WorkerIntervalMenit int
}

func Muat() Config {
	godotenv.Load()

	return Config{
		AppPort:             ambil("APP_PORT", ambil("PORT", "8080")),
		CORSOrigin:          ambilDaftar("CORS_ORIGIN", "http://localhost:5173"),
		DBHost:              ambil("DB_HOST", "localhost"),
		DBPort:              ambil("DB_PORT", "5432"),
		DBUser:              ambil("DB_USER", "postgres"),
		DBPassword:          ambil("DB_PASSWORD", ""),
		DBName:              ambil("DB_NAME", "latihan_chatbot"),
		DBSSLMode:           ambil("DB_SSLMODE", "disable"),
		AgentURL:            ambil("AGENT_URL", ""),
		AgentAPIKey:         ambil("AGENT_API_KEY", ""),
		IngestionPort:       ambil("INGESTION_PORT", "8081"),
		IngestionAPIKey:     ambil("INGESTION_API_KEY", ""),
		WorkerIntervalMenit: ambilAngka("WORKER_INTERVAL_MENIT", 1),
		SesiHari:            ambilAngka("SESI_HARI", 30),
		BatasTamuPerJam:     ambilAngka("BATAS_TAMU_PER_JAM", 60),
		BatasPesanPerMenit:  ambilAngka("BATAS_PESAN_PER_MENIT", 20),
	}
}

func (c Config) DSN() string {
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		c.DBHost, c.DBPort, c.DBUser, c.DBPassword, c.DBName, c.DBSSLMode)

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
