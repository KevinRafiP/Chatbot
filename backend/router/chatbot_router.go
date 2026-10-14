package router

import (
	"net/http"
	"time"

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
}

// BuatChatbot mendaftarkan semua endpoint layanan chatbot
func BuatChatbot(
	pengetahuanRepo *repository.PengetahuanRepository,
	chatbotService *service.ChatbotService,
	sesiService *service.SesiService,
	percakapanService *service.PercakapanService,
	akunService *service.AkunService,
	ingestionService *service.IngestionService,
	corsOrigin []string,
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

	pembatasTamu := middleware.BaruPembatas(batas.TamuPerJam, time.Hour)
	pembatasAkun := middleware.BaruPembatas(batas.AkunPerMenit, time.Minute)
	pembatasPesan := middleware.BaruPembatas(batas.PesanPerMenit, time.Minute)
	pembatasGlobal := middleware.BaruPembatas(batas.PesanGlobalMenit, time.Minute)
	pembatasPesanTamu := middleware.BaruPembatas(batas.PesanTamu, batas.MasaTamu)

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

	mux.Handle("POST /sesi/tamu", middleware.BatasiLaju(pembatasTamu, perIP, handler.MasukTamu(sesiService)))
	mux.Handle("GET /sesi", wajib(http.HandlerFunc(handler.SesiSaya)))
	mux.Handle("DELETE /sesi", wajib(handler.Keluar(sesiService)))

	mux.Handle("POST /akun/daftar", middleware.BatasiLaju(pembatasAkun, perIP, handler.Daftar(akunService)))
	mux.Handle("POST /akun/masuk", middleware.BatasiLaju(pembatasAkun, perIP, handler.Masuk(akunService)))

	// tamu hanya bisa chat; percakapannya tidak disimpan, riwayatnya dikirim dari browser
	mux.Handle("POST /tamu/pesan", wajib(
		middleware.BatasiLaju(pembatasPesan, perPengguna,
			middleware.BatasiTamu(pembatasPesanTamu,
				middleware.BatasiLaju(pembatasGlobal, semua, handler.ChatTamu(chatbotService))))))

	mux.Handle("GET /pengetahuan", admin(handler.DaftarPengetahuan(pengetahuanRepo)))
	mux.Handle("POST /admin/pengetahuan", admin(handler.IngestSatu(ingestionService)))
	mux.Handle("POST /admin/admin", admin(handler.JadikanAdmin(akunService)))

	mux.Handle("GET /percakapan", akun(handler.DaftarPercakapan(percakapanService)))
	mux.Handle("POST /percakapan", akun(handler.BuatPercakapan(percakapanService)))
	mux.Handle("DELETE /percakapan/{id}", akun(handler.HapusPercakapan(percakapanService)))
	mux.Handle("PATCH /percakapan/{id}", akun(handler.GantiNamaPercakapan(percakapanService)))
	mux.Handle("GET /percakapan/{id}/pesan", akun(handler.DaftarPesan(percakapanService)))
	mux.Handle("POST /percakapan/{id}/pesan",
		akun(middleware.BatasiLaju(pembatasPesan, perPengguna,
			middleware.BatasiLaju(pembatasGlobal, semua, handler.KirimPesan(percakapanService)))))

	return middleware.HeaderKeamanan(middleware.CORS(corsOrigin, middleware.BatasBody(256<<10, mux)))
}
