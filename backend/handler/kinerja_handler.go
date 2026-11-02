package handler

import (
	"errors"
	"log"
	"net/http"
	"strconv"

	"chatbot/backend/service"
)

// LaporanKinerja: GET /admin/kinerja?hari=7, hanya untuk admin; hari boleh 1, 7, atau 30
func LaporanKinerja(kinerja *service.KinerjaService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		hari, _ := strconv.Atoi(r.URL.Query().Get("hari"))
		laporan, err := kinerja.Laporan(hari)
		if errors.Is(err, service.ErrKinerjaMati) {
			writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "catatan kinerja dimatikan (KINERJA_SIMPAN_HARI=0)"})
			return
		}
		if err != nil {
			log.Println("error ambil laporan kinerja:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal mengambil laporan kinerja"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "laporan kinerja", Data: laporan})
	}
}
