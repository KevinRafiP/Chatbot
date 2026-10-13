package router

import (
	"net/http"
	"time"

	"chatbot/backend/handler"
	"chatbot/backend/middleware"
	"chatbot/backend/repository"
	"chatbot/backend/service"
)

// BuatChatbot mendaftarkan semua endpoint layanan chatbot
func BuatChatbot(
	pengetahuanRepo *repository.PengetahuanRepository,
	chatbotService *service.ChatbotService,
	sesiService *service.SesiService,
	percakapanService *service.PercakapanService,
	akunService *service.AkunService,
	ingestionService *service.IngestionService,
	corsOrigin []string,
	batasTamuPerJam int,
	batasPesanPerMenit int,
) http.Handler {
	mux := http.NewServeMux()

	// wajib membungkus handler agar hanya bisa dipakai pengguna yang punya sesi
	wajib := func(h http.Handler) http.Handler {
		return middleware.WajibSesi(sesiService, h)
	}
	// admin membungkus handler agar hanya bisa dipakai akun admin
	admin := func(h http.Handler) http.Handler {
		return middleware.WajibSesi(sesiService, middleware.WajibAdmin(h))
	}

	pembatasTamu := middleware.BaruPembatas(batasTamuPerJam, time.Hour)
	pembatasPesan := middleware.BaruPembatas(batasPesanPerMenit, time.Minute)
	pembatasAkun := middleware.BaruPembatas(30, time.Minute)

	// semua memakai satu kunci yang sama, jadi batasnya berlaku untuk seluruh pengunjung
	semua := func(r *http.Request) string {
		return "semua"
	}
	// perPengguna memakai id pengguna sebagai kunci, jadi tiap pengguna punya jatah sendiri
	perPengguna := func(r *http.Request) string {
		return middleware.PenggunaDari(r.Context()).ID
	}

	mux.HandleFunc("GET /kesehatan", handler.Kesehatan)

	mux.HandleFunc("GET /halo", handler.Halo)
	mux.HandleFunc("GET /sapa/{nama}", handler.Sapa)
	mux.HandleFunc("POST /pengguna", handler.BuatPengguna)

	mux.HandleFunc("GET /pengetahuan", handler.DaftarPengetahuan(pengetahuanRepo))
	mux.Handle("POST /chat", middleware.BatasiLaju(pembatasPesan, semua, handler.Chat(chatbotService)))

	mux.Handle("POST /sesi/tamu", middleware.BatasiLaju(pembatasTamu, semua, handler.MasukTamu(sesiService)))
	mux.Handle("GET /sesi", wajib(http.HandlerFunc(handler.SesiSaya)))
	mux.Handle("DELETE /sesi", wajib(handler.Keluar(sesiService)))

	mux.Handle("POST /akun/daftar", middleware.BatasiLaju(pembatasAkun, semua, handler.Daftar(akunService)))
	mux.Handle("POST /akun/masuk", middleware.BatasiLaju(pembatasAkun, semua, handler.Masuk(akunService)))

	mux.Handle("POST /admin/pengetahuan", admin(handler.IngestSatu(ingestionService)))
	mux.Handle("POST /admin/admin", admin(handler.JadikanAdmin(akunService)))

	mux.Handle("GET /percakapan", wajib(handler.DaftarPercakapan(percakapanService)))
	mux.Handle("POST /percakapan", wajib(handler.BuatPercakapan(percakapanService)))
	mux.Handle("DELETE /percakapan/{id}", wajib(handler.HapusPercakapan(percakapanService)))
	mux.Handle("PATCH /percakapan/{id}", wajib(handler.GantiNamaPercakapan(percakapanService)))
	mux.Handle("GET /percakapan/{id}/pesan", wajib(handler.DaftarPesan(percakapanService)))
	mux.Handle("POST /percakapan/{id}/pesan",
		wajib(middleware.BatasiLaju(pembatasPesan, perPengguna, handler.KirimPesan(percakapanService))))

	return middleware.CORS(corsOrigin, mux)
}
