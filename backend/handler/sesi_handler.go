package handler

import (
	"log"
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// MasukTamu: POST /sesi/tamu
func MasukTamu(sesi *service.SesiService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, pengguna, err := sesi.MasukTamu(r.UserAgent())
		if err != nil {
			log.Println("error masuk tamu:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal membuat sesi"})
			return
		}
		writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "masuk sebagai tamu",
			Data: map[string]any{"token": token, "pengguna": pengguna}})
	}
}

// SesiSaya: GET /sesi
func SesiSaya(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "sesi aktif", Data: middleware.PenggunaDari(r.Context())})
}

// Keluar: DELETE /sesi
func Keluar(sesi *service.SesiService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := sesi.Keluar(middleware.AmbilToken(r)); err != nil {
			log.Println("error keluar:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal menghapus sesi"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "sesi dihapus"})
	}
}
