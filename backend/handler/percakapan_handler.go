package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"regexp"
	"strings"

	"chatbot/backend/agen"
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

// GantiNamaPercakapan: PATCH /percakapan/{id} dengan body {"judul": "..."}
func GantiNamaPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Judul string `json:"judul"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 4<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		hasil, err := percakapan.GantiNama(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Judul)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "judul percakapan diganti", Data: hasil})
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

		var sse *penulisSSE
		var kabar agen.Kabar
		if mintaStream(r) {
			sse = &penulisSSE{w: w}
			kabar = sse.kabar
		}

		hasil, err := percakapan.Kirim(r.Context(), id, middleware.PenggunaDari(r.Context()).ID, permintaan.Pertanyaan, kabar)
		if sse != nil && sse.mulai {
			if err != nil {
				log.Println("error kirim pesan (stream):", err)
				sse.kirim("galat", Response{Status: "gagal", Message: "chatbot sedang bermasalah"})
				return
			}
			sse.kirim("selesai", hasil)
			return
		}
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "jawaban chatbot", Data: hasil})
	}
}

// FavoritPesan: PATCH /pesan/{id}/favorit dengan body {"favorit": true}
func FavoritPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Favorit bool `json:"favorit"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 1<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		if err := percakapan.TandaiFavorit(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Favorit); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "favorit diperbarui"})
	}
}

// DaftarFavorit: GET /pesan/favorit
func DaftarFavorit(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := percakapan.Favorit(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar pesan berbintang", Data: daftar})
	}
}

var polaUUID = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

// bacaID membaca {id} dari alamat; jika bentuknya bukan UUID, langsung membalas 400
func bacaID(w http.ResponseWriter, r *http.Request) (string, bool) {
	id := strings.ToLower(r.PathValue("id"))
	if !polaUUID.MatchString(id) {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "id tidak valid"})
		return "", false
	}
	return id, true
}

// gagalPercakapan memilih status dan pesan yang aman untuk tiap jenis error
func gagalPercakapan(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, service.ErrPercakapanTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "percakapan tidak ditemukan"})
	case errors.Is(err, service.ErrPesanTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "pesan tidak ditemukan"})
	case errors.Is(err, service.ErrDataTidakValid):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "pertanyaan wajib diisi, maksimal 2000 huruf"})
	case errors.Is(err, service.ErrJudulTidakValid):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "judul wajib diisi, maksimal 100 huruf"})
	default:
		log.Println("error percakapan:", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
	}
}
