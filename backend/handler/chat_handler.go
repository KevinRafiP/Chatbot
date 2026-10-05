package handler

import (
	"encoding/json"
	"log"
	"net/http"

	"chatbot/backend/service"
)

type PermintaanChat struct {
	Pertanyaan string `json:"pertanyaan"`
}

// Chat: POST /chat dengan body {"pertanyaan": "..."}
func Chat(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var permintaan PermintaanChat
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}
		if permintaan.Pertanyaan == "" {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "pertanyaan wajib diisi"})
			return
		}

		hasil, err := chatbot.Jawab(r.Context(), permintaan.Pertanyaan)
		if err != nil {
			log.Println("error chatbot:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "chatbot sedang bermasalah"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "jawaban chatbot", Data: hasil})
	}
}
