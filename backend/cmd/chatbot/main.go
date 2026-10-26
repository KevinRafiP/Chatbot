package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/email"
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
	// pengaturan embedding (penyedia, model, kemiripan minimal) ada di agent/.env
	embeddingService := service.BaruEmbeddingService(repository.BaruEmbeddingRepository(db), klienAgen)
	chatbotService := service.BaruChatbotService(pengetahuanRepo, klienAgen, embeddingService)

	sesiRepo := repository.BaruSesiRepository(db)
	masaSesi := time.Duration(cfg.SesiHari) * 24 * time.Hour
	masaTamu := time.Duration(cfg.SesiTamuJam) * time.Hour
	sesiService := service.BaruSesiService(sesiRepo, masaSesi, masaTamu)
	// link verifikasi mengarah ke frontend; bila FRONTEND_URL kosong dipakai CORS_ORIGIN yang pertama
	alamatFrontend := cfg.FrontendURL
	if alamatFrontend == "" && len(cfg.CORSOrigin) > 0 {
		alamatFrontend = cfg.CORSOrigin[0]
	}
	var pengirimEmail service.PengirimEmail
	switch cfg.EmailLayanan {
	case "brevo":
		pengirimEmail = email.BaruKlienBrevo(cfg.EmailAPIKey, cfg.EmailPengirim, cfg.NamaPengirim)
		log.Println("verifikasi email aktif (brevo), link ke:", alamatFrontend)
	case "":
		log.Println("EMAIL_LAYANAN kosong: akun baru langsung aktif tanpa verifikasi email")
	default:
		log.Fatal("EMAIL_LAYANAN tidak dikenal: ", cfg.EmailLayanan)
	}
	akunService := service.BaruAkunService(repository.BaruAkunRepository(db), sesiService, cfg.EmailAdmin,
		pengirimEmail, alamatFrontend)
	ingestionService := service.BaruIngestionService(pengetahuanRepo)
	ingatanService := service.BaruIngatanService(repository.BaruIngatanRepository(db), klienAgen)
	emailJawaban := service.BaruEmailJawabanService(pengirimEmail, cfg.EmailJawabanPerHari)
	if emailJawaban != nil {
		log.Println("kirim jawaban ke email aktif, maksimal per hari:", cfg.EmailJawabanPerHari)
	}
	percakapanService := service.BaruPercakapanService(repository.BaruPercakapanRepository(db), chatbotService, ingatanService, emailJawaban)

	intervalWorker := time.Duration(cfg.WorkerIntervalMenit) * time.Minute
	worker.JalankanSemua(context.Background(),
		worker.BaruPengindeksKataKunci(pengetahuanRepo, intervalWorker),
		worker.BaruPembersihSesi(sesiRepo, time.Hour),
		worker.BaruPengindeksEmbedding(embeddingService, intervalWorker),
	)

	batas := router.Batas{
		TamuPerJam:       cfg.BatasTamuPerJam,
		AkunPerMenit:     cfg.BatasAkunPerMenit,
		PesanPerMenit:    cfg.BatasPesanPerMenit,
		PesanGlobalMenit: cfg.BatasPesanGlobal,
		PesanTamu:        cfg.BatasPesanTamu,
		MasaTamu:         masaTamu,
		BerkasPerJam:     cfg.BatasBerkasPerJam,
		BerkasMaks:       int64(cfg.BerkasMaksMB) << 20,
	}
	mux := router.BuatChatbot(pengetahuanRepo, chatbotService, sesiService, percakapanService,
		akunService, ingestionService, cfg.CORSOrigin, cfg.AgentAPIKey, batas)

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
