package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"chatbot/backend/agen"
	"chatbot/backend/model"
	"chatbot/backend/service"
)

// batasBodyChat cukup untuk pertanyaan, riwayat tamu, dan teks lampiran
const batasBodyChat = 200 << 10

type PermintaanChat struct {
	Pertanyaan string          `json:"pertanyaan"`
	Mode       string          `json:"mode"`
	Lampiran   *model.Lampiran `json:"lampiran"`
}

type PermintaanTamu struct {
	Pertanyaan string                `json:"pertanyaan"`
	Riwayat    []service.RiwayatTamu `json:"riwayat"`
	Lampiran   *model.Lampiran       `json:"lampiran"`
}

// ChatTamu: POST /tamu/pesan dengan body {"pertanyaan": "...", "riwayat": [{"peran": "user", "teks": "..."}], "lampiran": {"nama": "...", "teks": "..."}}
func ChatTamu(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var permintaan PermintaanTamu
		r.Body = http.MaxBytesReader(w, r.Body, batasBodyChat)
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

		hasil, err := chatbot.JawabTamu(r.Context(), permintaan.Pertanyaan, permintaan.Riwayat, permintaan.Lampiran, kabar)
		if sse != nil && sse.mulai {
			if err != nil {
				log.Println("error chatbot tamu (stream):", err)
				sse.kirim("galat", Response{Status: "gagal", Message: "chatbot sedang bermasalah"})
				return
			}
			sse.kirim("selesai", hasil)
			return
		}
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
