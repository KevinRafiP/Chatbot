package main

import (
	"log"
	"net/http"

	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/repository"
	"chatbot/backend/router"
	"chatbot/backend/service"
)

func main() {
	cfg := config.Muat()
	if cfg.IngestionAPIKey == "" {
		log.Fatal("INGESTION_API_KEY wajib diisi di .env")
	}

	db, err := database.Hubungkan(cfg.DSN())
	if err != nil {
		log.Fatal("gagal terhubung ke database: ", err)
	}
	defer db.Close()
	log.Println("database terhubung")

	if err := database.JalankanMigrasi(db); err != nil {
		log.Fatal("migrasi gagal: ", err)
	}

	pengetahuanRepo := repository.BaruPengetahuanRepository(db)
	ingestionService := service.BaruIngestionService(pengetahuanRepo)

	mux := router.BuatIngestion(ingestionService, cfg.IngestionAPIKey)

	log.Println("layanan ingestion jalan di http://localhost:" + cfg.IngestionPort)
	log.Fatal(http.ListenAndServe(":"+cfg.IngestionPort, mux))
}
