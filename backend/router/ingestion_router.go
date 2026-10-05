package router

import (
	"net/http"

	"chatbot/backend/handler"
	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// BuatIngestion mendaftarkan semua endpoint layanan ingestion
func BuatIngestion(ingestionService *service.IngestionService, apiKey string) *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /kesehatan", handler.Kesehatan)

	mux.Handle("POST /ingestion/pengetahuan", middleware.WajibAPIKey(apiKey, handler.IngestSatu(ingestionService)))
	mux.Handle("POST /ingestion/pengetahuan/batch", middleware.WajibAPIKey(apiKey, handler.IngestBanyak(ingestionService)))

	return mux
}
