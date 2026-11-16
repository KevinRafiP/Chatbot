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

// KesehatanLengkap: GET /kesehatan/lengkap untuk pemantau uptime; membalas 503 bila agent mati.
// Database tidak dicek agar ping berkala tidak membangunkan Neon
func KesehatanLengkap(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !chatbot.AgenTerhubung(r.Context()) {
			writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "agent tidak membalas"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "backend dan agent aktif"})
	}
}
