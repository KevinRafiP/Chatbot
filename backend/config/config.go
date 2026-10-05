package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	AppPort             string
	DBHost              string
	DBPort              string
	DBUser              string
	DBPassword          string
	DBName              string
	DBSSLMode           string
	AgentURL            string
	AgentAPIKey         string
	IngestionPort       string
	IngestionAPIKey     string
	WorkerIntervalMenit int
}

func Muat() Config {
	godotenv.Load()

	return Config{
		AppPort:             ambil("APP_PORT", "8080"),
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
