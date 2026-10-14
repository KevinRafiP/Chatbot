package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"chatbot/backend/service"
)

type PermintaanChat struct {
	Pertanyaan string `json:"pertanyaan"`
}

type PermintaanTamu struct {
	Pertanyaan string                `json:"pertanyaan"`
	Riwayat    []service.RiwayatTamu `json:"riwayat"`
}

// ChatTamu: POST /tamu/pesan dengan body {"pertanyaan": "...", "riwayat": [{"peran": "user", "teks": "..."}]}
func ChatTamu(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var permintaan PermintaanTamu
		r.Body = http.MaxBytesReader(w, r.Body, 64<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		hasil, err := chatbot.JawabTamu(r.Context(), permintaan.Pertanyaan, permintaan.Riwayat)
		if errors.Is(err, service.ErrDataTidakValid) {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "pertanyaan wajib diisi (maksimal 2000 huruf) dan riwayat harus valid"})
			return
		}
		if err != nil {
			log.Println("error chatbot tamu:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "chatbot sedang bermasalah"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "jawaban chatbot", Data: hasil})
	}
}
