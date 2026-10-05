package router

import (
	"net/http"

	"chatbot/backend/handler"
	"chatbot/backend/repository"
	"chatbot/backend/service"
)

// BuatChatbot mendaftarkan semua endpoint layanan chatbot
func BuatChatbot(pengetahuanRepo *repository.PengetahuanRepository, chatbotService *service.ChatbotService) *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /kesehatan", handler.Kesehatan)

	mux.HandleFunc("GET /halo", handler.Halo)
	mux.HandleFunc("GET /sapa/{nama}", handler.Sapa)
	mux.HandleFunc("POST /pengguna", handler.BuatPengguna)

	mux.HandleFunc("GET /pengetahuan", handler.DaftarPengetahuan(pengetahuanRepo))
	mux.HandleFunc("POST /chat", handler.Chat(chatbotService))

	return mux
}
