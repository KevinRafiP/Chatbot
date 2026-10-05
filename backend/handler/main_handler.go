package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
)

type Pengguna struct {
	Nama string `json:"nama"`
	Umur int    `json:"umur"`
}

func Halo(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, "Halo dari server Go!")
}

// Sapa: GET /sapa/{nama}?umur=20
func Sapa(w http.ResponseWriter, r *http.Request) {
	nama := r.PathValue("nama")
	umurStr := r.URL.Query().Get("umur")

	if umurStr == "" {
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "Halo " + nama})
		return
	}

	umur, err := strconv.Atoi(umurStr)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "umur harus angka"})
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Status:  "sukses",
		Message: "Halo " + nama,
		Data:    map[string]int{"umur": umur},
	})
}

// BuatPengguna: POST /pengguna dengan body JSON
func BuatPengguna(w http.ResponseWriter, r *http.Request) {
	var p Pengguna
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
		return
	}
	if p.Nama == "" {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "nama wajib diisi"})
		return
	}

	writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "pengguna diterima", Data: p})
}
