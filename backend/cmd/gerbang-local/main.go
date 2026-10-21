package main

import (
	"crypto/subtle"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"

	"github.com/joho/godotenv"
)

// jalurDiizinkan adalah endpoint Ollama yang boleh dipakai dari luar, endpoint lain seperti pull dan delete ditolak
var jalurDiizinkan = map[string]bool{
	"/v1/chat/completions": true,
	"/v1/models":           true,
	"/v1/embeddings":       true,
}

func main() {
	_ = godotenv.Load()

	kunci := os.Getenv("GERBANG_LOCAL_KUNCI")
	if kunci == "" {
		log.Fatal("GERBANG_LOCAL_KUNCI wajib diisi di .env")
	}
	port := ambil("GERBANG_LOCAL_PORT", "8090")
	tujuan, err := url.Parse(ambil("GERBANG_LOCAL_TUJUAN", "http://127.0.0.1:11434"))
	if err != nil {
		log.Fatal("GERBANG_LOCAL_TUJUAN tidak valid: ", err)
	}

	proksi := &httputil.ReverseProxy{
		Rewrite: func(r *httputil.ProxyRequest) {
			// SetURL juga mengganti Host menjadi alamat Ollama, karena Ollama menolak Host dari luar
			r.SetURL(tujuan)
			r.Out.Header.Del("Authorization")
		},
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		if subtle.ConstantTimeCompare([]byte(token), []byte(kunci)) != 1 {
			http.Error(w, "kunci gerbang salah", http.StatusUnauthorized)
			return
		}
		if !jalurDiizinkan[r.URL.Path] {
			http.NotFound(w, r)
			return
		}
		proksi.ServeHTTP(w, r)
	})

	// hanya mendengar di 127.0.0.1, jadi dari luar laptop gerbang ini hanya bisa dicapai lewat tunnel
	log.Println("gerbang local jalan di http://127.0.0.1:" + port + " menuju " + tujuan.String())
	log.Fatal(http.ListenAndServe("127.0.0.1:"+port, mux))
}

func ambil(kunci, bawaan string) string {
	if nilai := os.Getenv(kunci); nilai != "" {
		return nilai
	}
	return bawaan
}
