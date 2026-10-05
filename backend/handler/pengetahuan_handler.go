package handler

import (
	"log"
	"net/http"

	"chatbot/backend/repository"
)

// DaftarPengetahuan: GET /pengetahuan
func DaftarPengetahuan(repo *repository.PengetahuanRepository) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := repo.Semua()
		if err != nil {
			log.Println("error ambil pengetahuan:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal mengambil data"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "data pengetahuan", Data: daftar})
	}
}
