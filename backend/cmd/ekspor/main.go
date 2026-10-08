package main

import (
	"context"
	"log"

	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/repository"
	"chatbot/backend/service"
)

func main() {
	cfg := config.Muat()

	db, err := database.Hubungkan(cfg.DSN())
	if err != nil {
		log.Fatal("gagal terhubung ke database: ", err)
	}
	defer db.Close()

	ekspor := service.BaruEksporService(repository.BaruEksporRepository(db),
		cfg.EksporFolder, cfg.EksporURL, cfg.EksporKunci, cfg.EksporDriveFolder)

	lokasi, terkirim, err := ekspor.Jalankan(context.Background())
	if lokasi != "" {
		log.Println("berkas ekspor tersimpan di", lokasi)
	}
	if err != nil {
		log.Fatal("ekspor gagal: ", err)
	}
	if terkirim {
		log.Println("berkas ekspor terkirim ke EKSPOR_URL")
	} else {
		log.Println("EKSPOR_URL kosong: berkas hanya disimpan di komputer ini")
	}
}
