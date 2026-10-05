package handler

import "net/http"

// Kesehatan: GET /kesehatan untuk mengecek layanan masih hidup
func Kesehatan(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "layanan aktif"})
}
