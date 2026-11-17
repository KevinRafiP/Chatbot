package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// AmbilInstruksi: GET /akun/instruksi; instruksi pribadi akun dan batas panjangnya
func AmbilInstruksi(ingatan *service.IngatanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		instruksi, err := ingatan.AmbilInstruksi(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			log.Println("error membaca instruksi pribadi:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "instruksi pribadi",
			Data: map[string]any{"instruksi": instruksi, "batas": service.BatasInstruksi}})
	}
}

// BatalkanInstruksi: POST /akun/instruksi/batalkan dengan body {"instruksi": "..."}, yaitu instruksi hasil perubahan lewat chat;
// mengembalikan versi sebelum perubahan itu
func BatalkanInstruksi(ingatan *service.IngatanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p struct {
			Instruksi string `json:"instruksi"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 16<<10)
		if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}
		instruksi, err := ingatan.BatalkanInstruksi(middleware.PenggunaDari(r.Context()).ID, p.Instruksi)
		switch {
		case errors.Is(err, service.ErrInstruksiBerubah):
			writeJSON(w, http.StatusConflict, Response{Status: "gagal", Message: err.Error()})
		case err != nil:
			log.Println("error membatalkan instruksi pribadi:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
		default:
			writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "instruksi pribadi dikembalikan",
				Data: map[string]any{"instruksi": instruksi, "batas": service.BatasInstruksi}})
		}
	}
}

// SimpanInstruksi: PATCH /akun/instruksi dengan body {"instruksi": "..."}; kosong berarti menghapusnya
func SimpanInstruksi(ingatan *service.IngatanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p struct {
			Instruksi string `json:"instruksi"`
		}
		// huruf non-Latin bisa 4 byte, jadi batas body lebih besar dari 1500 huruf
		r.Body = http.MaxBytesReader(w, r.Body, 16<<10)
		if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}
		instruksi, err := ingatan.SimpanInstruksi(middleware.PenggunaDari(r.Context()).ID, p.Instruksi)
		switch {
		case errors.Is(err, service.ErrInstruksiPanjang):
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: err.Error()})
		case err != nil:
			log.Println("error menyimpan instruksi pribadi:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
		default:
			writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "instruksi pribadi disimpan",
				Data: map[string]any{"instruksi": instruksi, "batas": service.BatasInstruksi}})
		}
	}
}
