package handler

import (
	"errors"
	"log"
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// GoogleAktif: GET /akun/google; frontend menampilkan tombol "Masuk dengan Google" hanya bila aktif
func GoogleAktif(google *service.MasukGoogle) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "masuk dengan Google",
			Data: map[string]bool{"aktif": google != nil}})
	}
}

// MulaiGoogle: POST /akun/google/mulai dengan body {"ingat": true}; membalas alamat halaman Google yang harus dibuka browser
func MulaiGoogle(google *service.MasukGoogle) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if google == nil {
			writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "masuk dengan Google belum diaktifkan"})
			return
		}
		var p struct {
			Ingat *bool `json:"ingat"`
		}
		if !bacaJSON(w, r, &p) {
			return
		}
		alamat, err := google.Mulai(middleware.AmbilToken(r), r.UserAgent(), p.Ingat == nil || *p.Ingat)
		if err != nil {
			log.Println("error mulai masuk Google:", err)
			writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "masuk dengan Google sedang tidak bisa dipakai"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "buka halaman Google", Data: map[string]string{"url": alamat}})
	}
}

// KembaliGoogle: GET /akun/google/kembali, dibuka Google setelah pengguna memilih akun; browser diarahkan ke frontend
func KembaliGoogle(google *service.MasukGoogle) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if google == nil {
			http.NotFound(w, r)
			return
		}
		q := r.URL.Query()
		w.Header().Set("Cache-Control", "no-store")
		http.Redirect(w, r, google.Kembali(r.Context(), q.Get("state"), q.Get("code"), q.Get("error")), http.StatusSeeOther)
	}
}

// TukarGoogle: POST /akun/google/tukar dengan body {"kode": "..."}; kode sekali pakai dari alamat frontend ditukar dengan sesi
func TukarGoogle(google *service.MasukGoogle) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if google == nil {
			writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "masuk dengan Google belum diaktifkan"})
			return
		}
		var p struct {
			Kode string `json:"kode"`
		}
		if !bacaJSON(w, r, &p) {
			return
		}
		token, ingat, pengguna, err := google.Tukar(p.Kode)
		if errors.Is(err, service.ErrKodeGoogleSalah) {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "berhasil masuk dengan Google",
			Data: map[string]any{"token": token, "pengguna": pengguna, "ingat": ingat}})
	}
}
