package main

import (
	"log"
	"net/http"

	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/logawal"
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

	migrasiBaru, jumlahMigrasi, err := database.JalankanMigrasi(db)
	if err != nil {
		log.Fatal("migrasi gagal: ", err)
	}

	pengetahuanRepo := repository.BaruPengetahuanRepository(db)
	ingestionService := service.BaruIngestionService(pengetahuanRepo)

	mux := router.BuatIngestion(ingestionService, cfg.IngestionAPIKey)

	tabel := logawal.Baru("Vokapas ingestion")
	tabel.Isi("Database", "terhubung ("+cfg.AlamatDatabase()+")")
	tabel.Isi("Migrasi", database.KeteranganMigrasi(migrasiBaru, jumlahMigrasi))
	tabel.Isi("Alamat", "http://localhost:"+cfg.IngestionPort)
	tabel.Cetak()
	log.Fatal(http.ListenAndServe(":"+cfg.IngestionPort, mux))
}
