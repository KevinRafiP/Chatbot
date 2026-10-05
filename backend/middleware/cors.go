package middleware

import (
	"net/http"
	"slices"
)

// CORS mengizinkan browser dari alamat frontend yang terdaftar untuk memanggil API ini
func CORS(asalDiizinkan []string, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		asal := r.Header.Get("Origin")
		if asal != "" && slices.Contains(asalDiizinkan, asal) {
			w.Header().Set("Access-Control-Allow-Origin", asal)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Max-Age", "600")
			w.Header().Add("Vary", "Origin")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		berikutnya.ServeHTTP(w, r)
	})
}
