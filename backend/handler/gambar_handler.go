package handler

import (
	"io"
	"net/http"

	"chatbot/backend/service"
)

// TeruskanGambar: GET /gambar?url=...&tanda=...; tambahkan &unduh=1 agar browser menyimpannya sebagai berkas.
// Gambar diambil dari situs asal setiap kali diminta dan tidak disimpan; browser menyimpannya di cache 7 hari
func TeruskanGambar(penerus *service.PenerusGambar) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		alamat := q.Get("url")
		if alamat == "" || !penerus.Cocok(alamat, q.Get("tanda")) {
			writeJSON(w, http.StatusForbidden, Response{Status: "gagal", Message: "tanda gambar tidak valid"})
			return
		}
		isi, jenis, err := penerus.Ambil(r.Context(), alamat)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, Response{Status: "gagal", Message: err.Error()})
			return
		}
		defer isi.Close()

		h := w.Header()
		h.Set("Content-Type", jenis)
		h.Set("Cache-Control", "public, max-age=604800, immutable")
		h.Set("Cross-Origin-Resource-Policy", "cross-origin")
		if q.Get("unduh") == "1" {
			h.Set("Content-Disposition", `attachment; filename="vokapas-gambar.`+service.EkstensiGambar(jenis)+`"`)
		}
		w.WriteHeader(http.StatusOK)
		io.Copy(w, isi)
	}
}
