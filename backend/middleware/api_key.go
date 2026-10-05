package middleware

import (
	"crypto/subtle"
	"net/http"
)

// WajibAPIKey hanya meneruskan request yang membawa header X-API-Key yang benar
func WajibAPIKey(kunci string, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		dikirim := r.Header.Get("X-API-Key")
		if subtle.ConstantTimeCompare([]byte(dikirim), []byte(kunci)) != 1 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"status":"gagal","message":"API key tidak valid"}`))
			return
		}
		berikutnya.ServeHTTP(w, r)
	})
}
