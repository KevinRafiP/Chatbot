package handler

import (
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// LupaPassword: POST /akun/lupa-password dengan body {"email": "..."}
func LupaPassword(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanAkun
		if !bacaJSON(w, r, &p) {
			return
		}
		if err := akun.LupaPassword(p.Email); err != nil {
			gagalAkun(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses",
			Message: "jika email terdaftar, link atur ulang password sudah dikirim"})
	}
}

// AturUlangPassword: POST /akun/atur-ulang dengan body {"token": "...", "password": "...", "ingat": true} dari link di email
func AturUlangPassword(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p struct {
			Token string `json:"token"`
			permintaanAkun
		}
		if !bacaJSON(w, r, &p) {
			return
		}
		token, pengguna, err := akun.AturUlangPassword(p.Token, p.Password, middleware.AmbilToken(r), r.UserAgent(), p.ingat())
		kirimSesi(w, http.StatusOK, "password diganti", token, pengguna, err)
	}
}
