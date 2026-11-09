package middleware

import (
	"errors"
	"log"
	"net/http"

	"chatbot/backend/captcha"
	"chatbot/backend/model"
	"chatbot/backend/service"
)

// WajibCaptcha hanya meneruskan request yang membawa token Turnstile sah di header X-Captcha-Token.
// Ditolak dengan 400, bukan 403, karena frontend membaca 403 di daftar/masuk sebagai email belum dikonfirmasi.
// turnstile nil berarti captcha mati, jadi request langsung diteruskan
func WajibCaptcha(turnstile *captcha.Turnstile, berikutnya http.Handler) http.Handler {
	if turnstile == nil {
		return berikutnya
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		err := turnstile.Periksa(r.Context(), r.Header.Get("X-Captcha-Token"), IPKlien(r))
		if errors.Is(err, captcha.ErrTokenKosong) || errors.Is(err, captcha.ErrTokenDitolak) {
			tolak(w, http.StatusBadRequest, err.Error())
			return
		}
		if err != nil {
			log.Println("error periksa captcha:", err)
			tolak(w, http.StatusInternalServerError, "server sedang bermasalah")
			return
		}
		berikutnya.ServeHTTP(w, r)
	})
}

// BatasiJatah menolak pesan baru bila jatah token harian akun itu atau semua pengguna sudah habis.
// Dipasang di dalam WajibSesi
func BatasiJatah(cek func(model.Pengguna) error, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		err := cek(PenggunaDari(r.Context()))
		if errors.Is(err, service.ErrJatahAkunHabis) || errors.Is(err, service.ErrJatahSemuaHabis) {
			tolak(w, http.StatusTooManyRequests, err.Error())
			return
		}
		if err != nil {
			// catatan kinerja yang gagal dibaca tidak boleh menghentikan chat
			log.Println("error periksa jatah token:", err)
		}
		berikutnya.ServeHTTP(w, r)
	})
}
