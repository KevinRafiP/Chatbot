package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"strings"
	"time"

	"chatbot/backend/agen"
	"chatbot/backend/captcha"
	"chatbot/backend/config"
	"chatbot/backend/database"
	"chatbot/backend/email"
	"chatbot/backend/logawal"
	"chatbot/backend/repository"
	"chatbot/backend/router"
	"chatbot/backend/service"
	"chatbot/backend/worker"
)

// lamaTungguAgen adalah batas menunggu agent menyala; di Render agent dan backend dijalankan bersamaan
const lamaTungguAgen = 30 * time.Second

func main() {
	cfg := config.Muat()
	// semua keterangan saat menyala dikumpulkan di sini lalu dicetak sekali sebagai tabel
	tabel := logawal.Baru("Vokapas backend")

	db, err := database.Hubungkan(cfg.DSN())
	if err != nil {
		log.Fatal("gagal terhubung ke database: ", err)
	}
	defer db.Close()
	tabel.Isi("Database", "terhubung ("+cfg.AlamatDatabase()+")")

	migrasiBaru, jumlahMigrasi, err := database.JalankanMigrasi(db)
	if err != nil {
		log.Fatal("migrasi gagal: ", err)
	}
	tabel.Isi("Migrasi", database.KeteranganMigrasi(migrasiBaru, jumlahMigrasi))

	// keduanya diisi setelah agent membalas, di bawah
	tabel.Isi("Agent", "-")
	tabel.Isi("Pencarian makna", "-")

	pengetahuanRepo := repository.BaruPengetahuanRepository(db)

	var klienAgen *agen.Klien
	if cfg.AgentURL != "" {
		klienAgen = agen.BaruKlien(cfg.AgentURL, cfg.AgentAPIKey)
		// model lokal yang membaca banyak halaman bisa butuh lebih dari 5 menit
		agen.BatasWaktuStream = time.Duration(cfg.AgentStreamMenit) * time.Minute
	}
	// pengaturan embedding (penyedia, model, kemiripan minimal) ada di agent/.env
	embeddingService := service.BaruEmbeddingService(repository.BaruEmbeddingRepository(db), klienAgen)
	kinerjaService := service.BaruKinerjaService(repository.BaruKinerjaRepository(db), cfg.KinerjaSimpanHari, cfg.KinerjaTampilkanIsi,
		cfg.KinerjaPerHalaman, cfg.KinerjaBarisAlat)
	chatbotService := service.BaruChatbotService(pengetahuanRepo, klienAgen, embeddingService, kinerjaService)

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
		tabel.Isi("Verifikasi email", "aktif (Brevo), link ke "+alamatFrontend)
	case "":
		tabel.Isi("Verifikasi email", "mati, akun baru langsung aktif")
	default:
		log.Fatal("EMAIL_LAYANAN tidak dikenal: ", cfg.EmailLayanan)
	}
	akunService := service.BaruAkunService(repository.BaruAkunRepository(db), sesiService, cfg.EmailAdmin,
		pengirimEmail, alamatFrontend)
	akunService.BatasiGagalMasuk(cfg.BatasGagalMasuk, time.Duration(cfg.JedaGagalMenit)*time.Minute)
	ingestionService := service.BaruIngestionService(pengetahuanRepo)
	ingatanService := service.BaruIngatanService(repository.BaruIngatanRepository(db), klienAgen)
	emailJawaban := service.BaruEmailJawabanService(pengirimEmail, cfg.EmailJawabanPerHari)
	tabel.Isi("Jawaban ke email", logawal.AktifMati(emailJawaban != nil, keteranganJika(emailJawaban != nil,
		fmt.Sprintf("maksimal %d per hari", cfg.EmailJawabanPerHari))))
	percakapanRepo := repository.BaruPercakapanRepository(db)
	ringkasanService := service.BaruRingkasanService(percakapanRepo, klienAgen, kinerjaService, cfg.RingkasanSetelah, cfg.RingkasanSisa)
	percakapanService := service.BaruPercakapanService(percakapanRepo, chatbotService, ingatanService, emailJawaban, ringkasanService)

	tabel.Isi("Ringkasan percakapan", logawal.AktifMati(ringkasanService != nil, keteranganJika(ringkasanService != nil,
		fmt.Sprintf("setelah %d pesan", cfg.RingkasanSetelah))))
	tabel.Isi("Catatan kinerja", logawal.AktifMati(kinerjaService != nil, keteranganJika(kinerjaService != nil,
		fmt.Sprintf("disimpan %d hari", cfg.KinerjaSimpanHari))))

	intervalWorker := time.Duration(cfg.WorkerIntervalMenit) * time.Minute
	tabel.Isif("Worker", "kata kunci dan embedding tiap %s, sesi tiap 1 jam", logawal.Durasi(intervalWorker))

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

	// jatah token dihitung dari catatan kinerja, jadi hanya bekerja bila KINERJA_SIMPAN_HARI lebih dari 0
	jatahService := service.BaruJatahService(repository.BaruKinerjaRepository(db), cfg.TokenHarianAkun, cfg.TokenHarianSemua)
	switch {
	case jatahService == nil:
		tabel.Isi("Jatah token harian", "mati")
	case kinerjaService == nil:
		tabel.Isi("Jatah token harian", "tidak bekerja karena KINERJA_SIMPAN_HARI=0")
	default:
		tabel.Isif("Jatah token harian", "per akun %s, total semua akun %s", angkaAtauBebas(cfg.TokenHarianAkun), angkaAtauBebas(cfg.TokenHarianSemua))
	}
	turnstile := captcha.BaruTurnstile(cfg.TurnstileRahasia, cfg.TurnstileURL)
	tabel.Isi("Captcha masuk akun", logawal.AktifMati(turnstile != nil, keteranganJika(turnstile != nil, "Turnstile")))
	tabel.Isif("Batas pesan", "%d/menit per pengguna, %d/menit total, tamu %d pesan", cfg.BatasPesanPerMenit, cfg.BatasPesanGlobal, cfg.BatasPesanTamu)
	tabel.Isif("Unggah berkas", "maksimal %d MB, %d per jam", cfg.BerkasMaksMB, cfg.BatasBerkasPerJam)
	tabel.Isi("CORS", strings.Join(cfg.CORSOrigin, ", "))

	mux := router.BuatChatbot(pengetahuanRepo, chatbotService, sesiService, percakapanService,
		akunService, ingestionService, kinerjaService, jatahService, turnstile, cfg.CORSOrigin, cfg.AgentAPIKey, batas)

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
	// port dibuka dulu agar Render melihat server hidup, sementara backend menunggu agent yang menyala bersamaan
	pendengar, err := net.Listen("tcp", server.Addr)
	if err != nil {
		log.Fatal("port tidak bisa dibuka: ", err)
	}
	tabel.Isi("Alamat", "http://localhost:"+cfg.AppPort)
	go func() {
		ctx := context.Background()
		tabel.Ganti("Agent", keadaanAgen(ctx, klienAgen))
		if embeddingService.Aktif() {
			if err := embeddingService.Perbarui(ctx); err != nil {
				log.Println("gagal membaca pengaturan embedding dari agent:", err)
			}
		}
		tabel.Ganti("Pencarian makna", keteranganEmbedding(klienAgen, embeddingService))
		tabel.Cetak()
		// worker dijalankan sesudah tabel, agar catatannya tidak menyela tabel
		worker.JalankanSemua(ctx,
			worker.BaruPengindeksKataKunci(pengetahuanRepo, intervalWorker),
			worker.BaruPembersihSesi(sesiRepo, time.Hour),
			worker.BaruPengindeksEmbedding(embeddingService, intervalWorker),
		)
	}()
	log.Fatal(server.Serve(pendengar))
}

// keadaanAgen menunggu agent membalas, paling lama lamaTungguAgen, lalu menjelaskan keadaannya
func keadaanAgen(ctx context.Context, klien *agen.Klien) string {
	if klien == nil {
		return "mati (AGENT_URL kosong), chatbot menjawab dari database saja"
	}
	batas := time.Now().Add(lamaTungguAgen)
	for {
		hidup, llm := klien.Periksa(ctx)
		switch {
		case hidup && llm:
			return "tersambung, model AI siap (" + klien.Alamat() + ")"
		case hidup:
			return "tersambung, tetapi model AI belum bisa dihubungi (" + klien.Alamat() + ")"
		case time.Now().After(batas):
			return "belum membalas setelah " + logawal.Durasi(lamaTungguAgen) + " (" + klien.Alamat() + ")"
		}
		time.Sleep(2 * time.Second)
	}
}

func keteranganEmbedding(klien *agen.Klien, embedding *service.EmbeddingService) string {
	if klien != nil && !embedding.Aktif() {
		return "mati, tabel embedding_potongan belum ada (pgvector belum terpasang)"
	}
	return embedding.Keterangan()
}

// alamatDatabase menulis host dan nama database tanpa password
func keteranganJika(aktif bool, keterangan string) string {
	if !aktif {
		return ""
	}
	return keterangan
}

func angkaAtauBebas(n int) string {
	if n <= 0 {
		return "tanpa batas"
	}
	return fmt.Sprint(n)
}
