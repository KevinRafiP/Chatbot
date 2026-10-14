package middleware

import (
	"net"
	"net/http"
	"strings"
)

// HeaderKeamanan menambahkan header yang mencegah browser salah membaca, menyematkan, atau membocorkan balasan API
func HeaderKeamanan(berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
		h.Set("Strict-Transport-Security", "max-age=31536000")
		h.Set("Cache-Control", "no-store")
		berikutnya.ServeHTTP(w, r)
	})
}

// BatasBody menolak body yang lebih besar dari maks byte, untuk semua endpoint
func BatasBody(maks int64, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.ContentLength > maks {
			tolak(w, http.StatusRequestEntityTooLarge, "data yang dikirim terlalu besar")
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, maks)
		berikutnya.ServeHTTP(w, r)
	})
}

// IPKlien mengambil alamat IP pengirim; di Render alamat asli ada di entri terakhir X-Forwarded-For
// yang ditambahkan oleh proxy Render, jadi entri awal yang bisa dipalsukan pengirim tidak dipakai
func IPKlien(r *http.Request) string {
	if diteruskan := r.Header.Get("X-Forwarded-For"); diteruskan != "" {
		bagian := strings.Split(diteruskan, ",")
		if ip := strings.TrimSpace(bagian[len(bagian)-1]); ip != "" {
			return ip
		}
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}
