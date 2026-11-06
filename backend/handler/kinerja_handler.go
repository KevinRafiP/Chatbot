package handler

import (
	"errors"
	"log"
	"net/http"
	"strconv"
	"time"

	"chatbot/backend/service"
)

// bacaRentang membaca ?hari=7 (1, 7, atau 30), atau ?dari=...&sampai=... dengan waktu RFC 3339 untuk tanggal pilihan sendiri;
// false berarti format tanggal salah dan balasan 400 sudah dikirim
func bacaRentang(w http.ResponseWriter, r *http.Request) (service.RentangKinerja, bool) {
	var rentang service.RentangKinerja
	dari, sampai := r.URL.Query().Get("dari"), r.URL.Query().Get("sampai")
	if dari == "" && sampai == "" {
		rentang.Hari, _ = strconv.Atoi(r.URL.Query().Get("hari"))
		if rentang.Hari <= 0 {
			rentang.Hari = 7
		}
		return rentang, true
	}
	// browser mengirim awal hari menurut jamnya sendiri, jadi tanggal sesuai zona waktu admin
	var errDari, errSampai error
	rentang.Dari, errDari = time.Parse(time.RFC3339, dari)
	rentang.Sampai, errSampai = time.Parse(time.RFC3339, sampai)
	if errDari != nil || errSampai != nil {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "format tanggal tidak valid"})
		return rentang, false
	}
	return rentang, true
}

// tulisGagalKinerja membalas error dari KinerjaService dengan status yang sesuai
func tulisGagalKinerja(w http.ResponseWriter, err error, pesan string) {
	switch {
	case errors.Is(err, service.ErrKinerjaMati):
		writeJSON(w, http.StatusServiceUnavailable, Response{Status: "gagal", Message: "catatan kinerja dimatikan (KINERJA_SIMPAN_HARI=0)"})
	case errors.Is(err, service.ErrAkunSalah):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "akun tidak valid"})
	case errors.Is(err, service.ErrRentangSalah):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "tanggal akhir harus setelah tanggal awal, paling lama 1 tahun"})
	default:
		log.Println("error "+pesan+":", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal " + pesan})
	}
}

// LaporanKinerja: GET /admin/kinerja?hari=7 atau ?dari=...&sampai=..., boleh ditambah &akun=<id akun, tamu, atau lain>;
// hanya untuk admin
func LaporanKinerja(kinerja *service.KinerjaService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		rentang, ok := bacaRentang(w, r)
		if !ok {
			return
		}
		laporan, err := kinerja.Laporan(rentang, r.URL.Query().Get("akun"))
		if err != nil {
			tulisGagalKinerja(w, err, "mengambil laporan kinerja")
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "laporan kinerja", Data: laporan})
	}
}

// TerbaruKinerja: GET /admin/kinerja/terbaru?hari=7&halaman=2 (atau dengan dari, sampai, dan akun); satu halaman tabel "Terbaru"
func TerbaruKinerja(kinerja *service.KinerjaService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		rentang, ok := bacaRentang(w, r)
		if !ok {
			return
		}
		halaman, _ := strconv.Atoi(r.URL.Query().Get("halaman"))
		hasil, err := kinerja.Terbaru(rentang, r.URL.Query().Get("akun"), halaman)
		if err != nil {
			tulisGagalKinerja(w, err, "mengambil catatan kinerja")
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "catatan kinerja", Data: hasil})
	}
}
