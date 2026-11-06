package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/service"
)

// maksHurufHasilKode adalah panjang paling banyak tiap bagian hasil; agent memotongnya lagi sebelum dibaca model
const maksHurufHasilKode = 32 << 10

// HasilKode: POST /kode/hasil dengan body {"id", "keluaran", "galat", "hasil"} dari browser yang menjalankan
// kode Python alat jalankan_python. id hanya dikirim agent ke stream jawaban milik pengguna itu
func HasilKode(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var hasil agen.HasilKode
		r.Body = http.MaxBytesReader(w, r.Body, 4*maksHurufHasilKode)
		if err := json.NewDecoder(r.Body).Decode(&hasil); err != nil || strings.TrimSpace(hasil.ID) == "" || len(hasil.ID) > 100 {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "hasil kode tidak valid"})
			return
		}
		hasil.Keluaran = potongHuruf(hasil.Keluaran, maksHurufHasilKode)
		hasil.Galat = potongHuruf(hasil.Galat, maksHurufHasilKode)
		hasil.Hasil = potongHuruf(hasil.Hasil, maksHurufHasilKode)

		err := chatbot.KirimHasilKode(r.Context(), hasil)
		var ditolak agen.GalatDitolak
		switch {
		case errors.Is(err, service.ErrAgentMati):
			writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "agent tidak aktif"})
		case errors.As(err, &ditolak) && ditolak.Status == http.StatusNotFound:
			// jawaban sudah selesai, dihentikan, atau batas waktunya lewat
			writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "kode ini tidak sedang ditunggu"})
		case err != nil:
			log.Println("gagal meneruskan hasil kode:", err)
			writeJSON(w, http.StatusBadGateway, Response{Status: "gagal", Message: "hasil kode gagal diteruskan"})
		default:
			writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "hasil kode diterima"})
		}
	}
}

// potongHuruf memotong teks paling banyak maks byte tanpa merusak huruf UTF-8 di ujungnya
func potongHuruf(teks string, maks int) string {
	if len(teks) <= maks {
		return teks
	}
	return strings.ToValidUTF8(teks[:maks], "")
}
