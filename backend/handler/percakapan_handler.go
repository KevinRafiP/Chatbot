package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strconv"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// DaftarPercakapan: GET /percakapan
func DaftarPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := percakapan.Daftar(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar percakapan", Data: daftar})
	}
}

// BuatPercakapan: POST /percakapan
func BuatPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		baru, err := percakapan.Buat(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "percakapan dibuat", Data: baru})
	}
}

// HapusPercakapan: DELETE /percakapan/{id}
func HapusPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		if err := percakapan.Hapus(id, middleware.PenggunaDari(r.Context()).ID); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "percakapan dihapus"})
	}
}

// DaftarPesan: GET /percakapan/{id}/pesan
func DaftarPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		daftar, err := percakapan.Pesan(id, middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar pesan", Data: daftar})
	}
}

// KirimPesan: POST /percakapan/{id}/pesan dengan body {"pertanyaan": "..."}
func KirimPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan PermintaanChat
		r.Body = http.MaxBytesReader(w, r.Body, 16<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		hasil, err := percakapan.Kirim(r.Context(), id, middleware.PenggunaDari(r.Context()).ID, permintaan.Pertanyaan)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "jawaban chatbot", Data: hasil})
	}
}

// bacaID membaca {id} dari alamat; jika bukan angka, langsung membalas 400
func bacaID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "id percakapan tidak valid"})
		return 0, false
	}
	return id, true
}

// gagalPercakapan memilih status dan pesan yang aman untuk tiap jenis error
func gagalPercakapan(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, service.ErrPercakapanTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "percakapan tidak ditemukan"})
	case errors.Is(err, service.ErrDataTidakValid):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "pertanyaan wajib diisi, maksimal 2000 huruf"})
	default:
		log.Println("error percakapan:", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
	}
}
