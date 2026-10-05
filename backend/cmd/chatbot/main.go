package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/repository"
	"chatbot/backend/router"
	"chatbot/backend/service"
	"chatbot/backend/worker"
)

func main() {
	cfg := config.Muat()

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

	var klienAgen *agen.Klien
	if cfg.AgentURL != "" {
		klienAgen = agen.BaruKlien(cfg.AgentURL, cfg.AgentAPIKey)
		log.Println("agent aktif:", cfg.AgentURL)
	} else {
		log.Println("AGENT_URL kosong: chatbot menjawab dari database saja")
	}
	chatbotService := service.BaruChatbotService(pengetahuanRepo, klienAgen)

	intervalWorker := time.Duration(cfg.WorkerIntervalMenit) * time.Minute
	worker.JalankanSemua(context.Background(),
		worker.BaruPengindeksKataKunci(pengetahuanRepo, intervalWorker),
	)

	mux := router.BuatChatbot(pengetahuanRepo, chatbotService)

	log.Println("chatbot jalan di http://localhost:" + cfg.AppPort)
	log.Fatal(http.ListenAndServe(":"+cfg.AppPort, mux))
}
