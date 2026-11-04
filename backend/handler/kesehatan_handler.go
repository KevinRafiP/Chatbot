package handler

import (
	"net/http"

	"chatbot/backend/service"
)

// Kesehatan: GET /kesehatan untuk mengecek layanan masih hidup
func Kesehatan(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "layanan aktif"})
}

// StatusAgen: GET /status-agen untuk memberi tahu frontend apakah agent dan model AI-nya sedang bisa menjawab
func StatusAgen(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "status agent",
			Data: map[string]bool{"terhubung": chatbot.AgenTerhubung(r.Context())}})
	}
}
