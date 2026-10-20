package handler

import (
	"encoding/json"
	"errors"
	"log"
	"net/http"

	"chatbot/backend/middleware"
	"chatbot/backend/model"
	"chatbot/backend/service"
)

type permintaanAkun struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Ingat    *bool  `json:"ingat"`
}

// ingat bernilai true bila "ingat" tidak dikirim, agar frontend lama tetap mendapat sesi panjang
func (p permintaanAkun) ingat() bool {
	return p.Ingat == nil || *p.Ingat
}

// Daftar: POST /akun/daftar dengan body {"email": "...", "password": "..."}
func Daftar(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanAkun
		if !bacaJSON(w, r, &p) {
			return
		}
		token, pengguna, err := akun.Daftar(p.Email, p.Password, middleware.AmbilToken(r), r.UserAgent(), p.ingat())
		if err == nil && token == "" {
			writeJSON(w, http.StatusAccepted, Response{Status: "sukses", Message: "cek email untuk verifikasi",
				Data: map[string]any{"perlu_verifikasi": true, "email": pengguna.Email}})
			return
		}
		kirimSesi(w, http.StatusCreated, "akun dibuat", token, pengguna, err)
	}
}

// Masuk: POST /akun/masuk dengan body {"email": "...", "password": "..."}
func Masuk(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanAkun
		if !bacaJSON(w, r, &p) {
			return
		}
		token, pengguna, err := akun.Masuk(p.Email, p.Password, middleware.AmbilToken(r), r.UserAgent(), p.ingat())
		kirimSesi(w, http.StatusOK, "berhasil masuk", token, pengguna, err)
	}
}

// JadikanAdmin: POST /admin/admin dengan body {"email": "..."}, hanya untuk admin
func JadikanAdmin(akun *service.AkunService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanAkun
		if !bacaJSON(w, r, &p) {
			return
		}
		if err := akun.JadikanAdmin(p.Email); err != nil {
			gagalAkun(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "akun dijadikan admin"})
	}
}

func bacaJSON(w http.ResponseWriter, r *http.Request, tujuan any) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 4<<10)
	if err := json.NewDecoder(r.Body).Decode(tujuan); err != nil {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
		return false
	}
	return true
}

func kirimSesi(w http.ResponseWriter, status int, pesan, token string, pengguna model.Pengguna, err error) {
	if err != nil {
		gagalAkun(w, err)
		return
	}
	writeJSON(w, status, Response{Status: "sukses", Message: pesan,
		Data: map[string]any{"token": token, "pengguna": pengguna}})
}

// gagalAkun memilih status dan pesan yang aman untuk tiap jenis error akun
func gagalAkun(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, service.ErrEmailTidakValid), errors.Is(err, service.ErrPasswordTidakValid),
		errors.Is(err, service.ErrTokenVerifikasiSalah), errors.Is(err, service.ErrTokenAturUlangSalah):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrEmailSudahAda):
		writeJSON(w, http.StatusConflict, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrLoginSalah):
		writeJSON(w, http.StatusUnauthorized, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrAkunTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrEmailBelumDiverifikasi):
		writeJSON(w, http.StatusForbidden, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrGagalKirimEmail), errors.Is(err, service.ErrGagalKirimAturUlang):
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrEmailTidakAktif):
		writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: err.Error()})
	default:
		log.Println("error akun:", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
	}
}
