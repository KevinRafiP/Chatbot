package handler

import (
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"path/filepath"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/service"
)

// BacaBerkas: POST /berkas dengan form multipart berisi satu berkas di field "berkas".
// Berkas tidak disimpan; teksnya dikembalikan ke browser untuk dikirim bersama pesan berikutnya
func BacaBerkas(chatbot *service.ChatbotService, maks int64) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bagian, err := ambilBerkas(r)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "kirim satu berkas di field berkas"})
			return
		}
		defer bagian.Close()

		isi, err := io.ReadAll(io.LimitReader(bagian, maks+1))
		if err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "berkas gagal dibaca"})
			return
		}
		if int64(len(isi)) > maks {
			writeJSON(w, http.StatusRequestEntityTooLarge, Response{Status: "gagal", Message: "berkas terlalu besar"})
			return
		}
		if len(isi) == 0 {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "berkas kosong"})
			return
		}

		hasil, err := chatbot.BacaBerkas(r.Context(), filepath.Base(bagian.FileName()), isi)
		var ditolak agen.GalatDitolak
		switch {
		case errors.Is(err, service.ErrAgentMati):
			writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "membaca berkas belum aktif"})
		case errors.As(err, &ditolak) && ditolak.Status == http.StatusBadRequest:
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: ditolak.Pesan})
		case err != nil:
			log.Println("gagal membaca berkas:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "berkas gagal dibaca, coba lagi"})
		default:
			writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "isi berkas", Data: hasil})
		}
	}
}

// ambilBerkas membaca bagian multipart pertama yang bernama "berkas" tanpa menyimpannya ke disk
func ambilBerkas(r *http.Request) (interface {
	io.ReadCloser
	FileName() string
}, error) {
	pembaca, err := r.MultipartReader()
	if err != nil {
		return nil, err
	}
	for {
		bagian, err := pembaca.NextPart()
		if err != nil {
			return nil, err
		}
		if bagian.FormName() == "berkas" && strings.TrimSpace(bagian.FileName()) != "" {
			return bagian, nil
		}
		bagian.Close()
	}
}

// CariPengetahuanInternal: POST /internal/pengetahuan/cari dengan body {"kueri": "..."}, khusus agent (header X-API-Key)
func CariPengetahuanInternal(chatbot *service.ChatbotService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var permintaan struct {
			Kueri string `json:"kueri"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 4<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil || strings.TrimSpace(permintaan.Kueri) == "" {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "kueri wajib diisi"})
			return
		}
		hasil, err := chatbot.CariPengetahuan(r.Context(), permintaan.Kueri)
		if err != nil {
			log.Println("gagal mencari pengetahuan untuk agent:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "pencarian gagal"})
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "hasil pencarian", Data: hasil})
	}
}
