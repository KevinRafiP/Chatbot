package handler

import (
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// VerifikasiEmail: POST /akun/verifikasi dengan body {"token": "..."} dari link di email
func VerifikasiEmail(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p struct {
			Token string `json:"token"`
		}
		if !bacaJSON(w, r, &p) {
			return
		}
		token, pengguna, ingat, err := akun.Verifikasi(p.Token, middleware.AmbilToken(r), r.UserAgent())
		if err != nil {
			gagalAkun(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "email terverifikasi",
			Data: map[string]any{"token": token, "pengguna": pengguna, "ingat": ingat}})
	}
}

// KirimUlangVerifikasi: POST /akun/kirim-ulang dengan body {"email": "...", "ingat": true}
func KirimUlangVerifikasi(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanAkun
		if !bacaJSON(w, r, &p) {
			return
		}
		if err := akun.KirimUlang(p.Email, p.ingat()); err != nil {
			gagalAkun(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses",
			Message: "jika email terdaftar dan belum diverifikasi, link baru sudah dikirim"})
	}
}
