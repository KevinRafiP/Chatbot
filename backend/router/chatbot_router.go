package router

import (
	"net/http"
	"time"

	"chatbot/backend/captcha"
	"chatbot/backend/handler"
	"chatbot/backend/middleware"
	"chatbot/backend/repository"
	"chatbot/backend/service"
)

// Batas berisi semua batas jumlah permintaan yang dibaca dari .env
type Batas struct {
	TamuPerJam       int           // sesi tamu baru per IP per jam
	AkunPerMenit     int           // percobaan daftar/masuk per IP per menit
	PesanPerMenit    int           // pesan per pengguna per menit
	PesanGlobalMenit int           // pesan dari semua pengguna per menit, agar LLM tidak kebanjiran
	PesanTamu        int           // pesan per tamu selama masa sesinya
	MasaTamu         time.Duration // lama sesi tamu, dipakai sebagai jendela batas pesan tamu
	BerkasPerJam     int           // unggah berkas per pengguna per jam
	BerkasMaks       int64         // ukuran berkas maksimal dalam byte; 0 = unggah berkas mati
}

// BuatChatbot mendaftarkan semua endpoint layanan chatbot
func BuatChatbot(
	pengetahuanRepo *repository.PengetahuanRepository,
	chatbotService *service.ChatbotService,
	sesiService *service.SesiService,
	percakapanService *service.PercakapanService,
	akunService *service.AkunService,
	ingestionService *service.IngestionService,
	kinerjaService *service.KinerjaService,
	jatahService *service.JatahService,
	turnstile *captcha.Turnstile,
	corsOrigin []string,
	kunciAgent string,
	batas Batas,
) http.Handler {
	mux := http.NewServeMux()

	// wajib membungkus handler agar hanya bisa dipakai pengguna yang punya sesi
	wajib := func(h http.Handler) http.Handler {
		return middleware.WajibSesi(sesiService, h)
	}
	// akun membungkus handler agar hanya bisa dipakai akun terdaftar, bukan tamu
	akun := func(h http.Handler) http.Handler {
		return middleware.WajibSesi(sesiService, middleware.WajibAkun(h))
	}
	// admin membungkus handler agar hanya bisa dipakai akun admin
	admin := func(h http.Handler) http.Handler {
		return middleware.WajibSesi(sesiService, middleware.WajibAdmin(h))
	}

	// captcha hanya di masuk akun, agar bot tidak bisa menebak password; tanpa TURNSTILE_SECRET handler diteruskan apa adanya
	captchaWajib := func(h http.Handler) http.Handler {
		return middleware.WajibCaptcha(turnstile, h)
	}
	// jatah token harian per akun dan untuk semua pengguna, dicek sebelum pesan diteruskan ke agent
	jatah := func(h http.Handler) http.Handler {
		return middleware.BatasiJatah(jatahService.Cek, h)
	}

	pembatasTamu := middleware.BaruPembatas(batas.TamuPerJam, time.Hour)
	pembatasAkun := middleware.BaruPembatas(batas.AkunPerMenit, time.Minute)
	pembatasPesan := middleware.BaruPembatas(batas.PesanPerMenit, time.Minute)
	pembatasGlobal := middleware.BaruPembatas(batas.PesanGlobalMenit, time.Minute)
	pembatasPesanTamu := middleware.BaruPembatas(batas.PesanTamu, batas.MasaTamu)
	pembatasBerkas := middleware.BaruPembatas(batas.BerkasPerJam, time.Hour)

	// semua memakai satu kunci yang sama, jadi batasnya berlaku untuk seluruh pengunjung
	semua := func(r *http.Request) string {
		return "semua"
	}
	// perIP memakai alamat IP sebagai kunci, jadi tiap perangkat/jaringan punya jatah sendiri
	perIP := func(r *http.Request) string {
		return middleware.IPKlien(r)
	}
	// perPengguna memakai id pengguna sebagai kunci, jadi tiap pengguna punya jatah sendiri
	perPengguna := func(r *http.Request) string {
		return middleware.PenggunaDari(r.Context()).ID
	}

	mux.HandleFunc("GET /kesehatan", handler.Kesehatan)
	mux.HandleFunc("GET /status-agen", handler.StatusAgen(chatbotService))

	mux.Handle("POST /sesi/tamu", middleware.BatasiLaju(pembatasTamu, perIP, handler.MasukTamu(sesiService)))
	mux.Handle("GET /sesi", wajib(http.HandlerFunc(handler.SesiSaya)))
	mux.Handle("DELETE /sesi", wajib(handler.Keluar(sesiService)))

	mux.Handle("POST /akun/daftar", middleware.BatasiLaju(pembatasAkun, perIP, handler.Daftar(akunService)))
	mux.Handle("POST /akun/masuk", middleware.BatasiLaju(pembatasAkun, perIP, captchaWajib(handler.Masuk(akunService))))
	mux.Handle("POST /akun/verifikasi", middleware.BatasiLaju(pembatasAkun, perIP, handler.VerifikasiEmail(akunService)))
	mux.Handle("POST /akun/kirim-ulang", middleware.BatasiLaju(pembatasAkun, perIP, handler.KirimUlangVerifikasi(akunService)))
	mux.Handle("POST /akun/lupa-password", middleware.BatasiLaju(pembatasAkun, perIP, handler.LupaPassword(akunService)))
	mux.Handle("POST /akun/atur-ulang", middleware.BatasiLaju(pembatasAkun, perIP, handler.AturUlangPassword(akunService)))

	// tamu hanya bisa chat; percakapannya tidak disimpan, riwayatnya dikirim dari browser
	mux.Handle("POST /tamu/pesan", wajib(
		middleware.BatasiLaju(pembatasPesan, perPengguna,
			middleware.BatasiTamu(pembatasPesanTamu,
				jatah(middleware.BatasiLaju(pembatasGlobal, semua, handler.ChatTamu(chatbotService)))))))

	// hasil alat jalankan_python dari browser yang menjalankan kodenya (Pyodide), untuk tamu dan akun
	mux.Handle("POST /kode/hasil", wajib(handler.HasilKode(chatbotService)))

	mux.Handle("GET /pengetahuan", admin(handler.DaftarPengetahuan(pengetahuanRepo)))
	mux.Handle("POST /admin/pengetahuan", admin(handler.IngestSatu(ingestionService)))
	mux.Handle("POST /admin/admin", admin(handler.JadikanAdmin(akunService)))
	mux.Handle("GET /admin/kinerja", admin(handler.LaporanKinerja(kinerjaService)))
	mux.Handle("GET /admin/kinerja/terbaru", admin(handler.TerbaruKinerja(kinerjaService)))

	mux.Handle("GET /percakapan", akun(handler.DaftarPercakapan(percakapanService)))
	mux.Handle("GET /percakapan/cari", akun(handler.CariPercakapan(percakapanService)))
	mux.Handle("POST /percakapan", akun(handler.BuatPercakapan(percakapanService)))
	mux.Handle("DELETE /percakapan/{id}", akun(handler.HapusPercakapan(percakapanService)))
	mux.Handle("PATCH /percakapan/{id}", akun(handler.GantiNamaPercakapan(percakapanService)))
	mux.Handle("PATCH /percakapan/{id}/sematkan", akun(handler.SematkanPercakapan(percakapanService)))
	mux.Handle("GET /percakapan/{id}/pesan", akun(handler.DaftarPesan(percakapanService)))
	mux.Handle("GET /pesan/favorit", akun(handler.DaftarFavorit(percakapanService)))
	mux.Handle("PATCH /pesan/{id}/favorit", akun(handler.FavoritPesan(percakapanService)))
	mux.Handle("PATCH /pesan/{id}/penilaian", akun(handler.NilaiPesan(percakapanService)))
	mux.Handle("POST /percakapan/{id}/pesan",
		akun(middleware.BatasiLaju(pembatasPesan, perPengguna,
			jatah(middleware.BatasiLaju(pembatasGlobal, semua, handler.KirimPesan(percakapanService))))))
	// jawaban dibuat di server tanpa bergantung koneksi browser, jadi browser bisa menyambung lagi atau menghentikannya
	mux.Handle("GET /percakapan/{id}/jawaban", akun(handler.SambungJawaban(percakapanService)))
	mux.Handle("POST /percakapan/{id}/berhenti", akun(handler.HentikanJawaban(percakapanService)))
	// arahan tambahan saat AI masih menjawab: jawabannya dibuat ulang, jadi dihitung seperti pesan baru
	mux.Handle("POST /percakapan/{id}/arahan",
		akun(middleware.BatasiLaju(pembatasPesan, perPengguna,
			jatah(middleware.BatasiLaju(pembatasGlobal, semua, handler.ArahkanJawaban(percakapanService))))))

	// dipanggil alat cari_pengetahuan di agent; tanpa AGENT_API_KEY jalurnya tidak dibuka
	if kunciAgent != "" {
		mux.Handle("POST /internal/pengetahuan/cari", middleware.WajibAPIKey(kunciAgent, handler.CariPengetahuanInternal(chatbotService)))
	}

	// semua endpoint dibatasi 256 KB, kecuali unggah berkas yang punya batas sendiri
	akar := http.NewServeMux()
	akar.Handle("/", middleware.BatasBody(256<<10, mux))
	if batas.BerkasMaks > 0 {
		akar.Handle("POST /berkas", middleware.BatasBody(batas.BerkasMaks+64<<10, wajib(
			middleware.BatasiLaju(pembatasBerkas, perPengguna, handler.BacaBerkas(chatbotService, batas.BerkasMaks)))))
	}
	return middleware.HeaderKeamanan(middleware.CORS(corsOrigin, akar))
}
