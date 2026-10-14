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

	sesiRepo := repository.BaruSesiRepository(db)
	masaSesi := time.Duration(cfg.SesiHari) * 24 * time.Hour
	masaTamu := time.Duration(cfg.SesiTamuJam) * time.Hour
	sesiService := service.BaruSesiService(sesiRepo, masaSesi, masaTamu)
	akunService := service.BaruAkunService(repository.BaruAkunRepository(db), sesiService, cfg.EmailAdmin)
	ingestionService := service.BaruIngestionService(pengetahuanRepo)
	ingatanService := service.BaruIngatanService(repository.BaruIngatanRepository(db), klienAgen)
	percakapanService := service.BaruPercakapanService(repository.BaruPercakapanRepository(db), chatbotService, ingatanService)

	intervalWorker := time.Duration(cfg.WorkerIntervalMenit) * time.Minute
	worker.JalankanSemua(context.Background(),
		worker.BaruPengindeksKataKunci(pengetahuanRepo, intervalWorker),
		worker.BaruPembersihSesi(sesiRepo, time.Hour),
	)

	batas := router.Batas{
		TamuPerJam:       cfg.BatasTamuPerJam,
		AkunPerMenit:     cfg.BatasAkunPerMenit,
		PesanPerMenit:    cfg.BatasPesanPerMenit,
		PesanGlobalMenit: cfg.BatasPesanGlobal,
		PesanTamu:        cfg.BatasPesanTamu,
		MasaTamu:         masaTamu,
	}
	mux := router.BuatChatbot(pengetahuanRepo, chatbotService, sesiService, percakapanService,
		akunService, ingestionService, cfg.CORSOrigin, batas)

	// batas waktu membaca request mencegah koneksi lambat (slowloris) menahan server terlalu lama;
	// WriteTimeout tidak dipasang karena jawaban agent bisa butuh lebih dari satu menit
	server := &http.Server{
		Addr:              ":" + cfg.AppPort,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		IdleTimeout:       120 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}
	log.Println("chatbot jalan di http://localhost:" + cfg.AppPort)
	log.Fatal(server.ListenAndServe())
}
