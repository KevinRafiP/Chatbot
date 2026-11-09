package handler

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"regexp"
	"strings"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

// DaftarPercakapan: GET /percakapan
func DaftarPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := percakapan.Daftar(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar percakapan", Data: daftar})
	}
}

// BuatPercakapan: POST /percakapan
func BuatPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		baru, err := percakapan.Buat(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "percakapan dibuat", Data: baru})
	}
}

// HapusPercakapan: DELETE /percakapan/{id}
func HapusPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		if err := percakapan.Hapus(id, middleware.PenggunaDari(r.Context()).ID); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "percakapan dihapus"})
	}
}

// GantiNamaPercakapan: PATCH /percakapan/{id} dengan body {"judul": "..."}
func GantiNamaPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Judul string `json:"judul"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 4<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		hasil, err := percakapan.GantiNama(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Judul)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "judul percakapan diganti", Data: hasil})
	}
}

// DaftarPesan: GET /percakapan/{id}/pesan
func DaftarPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		daftar, err := percakapan.Pesan(id, middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar pesan", Data: daftar})
	}
}

// KirimPesan: POST /percakapan/{id}/pesan dengan body {"pertanyaan": "...", "mode": "cepat" | "mendalam", "lampiran": {"nama": "...", "teks": "..."}}
func KirimPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan PermintaanChat
		r.Body = http.MaxBytesReader(w, r.Body, batasBodyChat)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		jawaban, err := percakapan.Mulai(id, middleware.PenggunaDari(r.Context()), permintaan.Pertanyaan, permintaan.Mode, permintaan.Lampiran)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		alirkanJawaban(w, r, jawaban, false)
	}
}

// SambungJawaban: GET /percakapan/{id}/jawaban; menyambung ke jawaban yang masih dibuat, misalnya setelah refresh.
// Event pertama "mulai" berisi pertanyaannya, lalu semua kabar dari awal. Jawaban yang baru gagal juga dikirim,
// diakhiri "galat", agar pertanyaannya tampil dengan tanda gagal. 204 jika tidak ada keduanya
func SambungJawaban(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		jawaban := percakapan.JawabanBerjalan(id, middleware.PenggunaDari(r.Context()).ID)
		if jawaban == nil {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		alirkanJawaban(w, r, jawaban, true)
	}
}

// HentikanJawaban: POST /percakapan/{id}/berhenti; jawaban tidak lagi berhenti saat browser memutus koneksi
func HentikanJawaban(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		pesan := "tidak ada jawaban yang sedang dibuat"
		if percakapan.Hentikan(id, middleware.PenggunaDari(r.Context()).ID) {
			pesan = "jawaban dihentikan"
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: pesan})
	}
}

// alirkanJawaban mengirim kabar jawaban ke browser sampai selesai atau browser pergi; jawabannya sendiri tetap berjalan.
// sambung true untuk browser yang datang belakangan: info pertanyaan dikirim dulu, dan kode Python lama tidak dijalankan lagi
func alirkanJawaban(w http.ResponseWriter, r *http.Request, jawaban *service.JawabanBerjalan, sambung bool) {
	if !mintaStream(r) {
		hasil, err := jawaban.Tunggu(r.Context())
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "jawaban chatbot", Data: hasil})
		return
	}

	sse := &penulisSSE{w: w}
	defer sse.jaga()()
	if sambung {
		// selesai true bila jawaban ini sudah gagal, agar browser tidak menampilkannya sebagai jawaban yang masih ditulis
		sse.kirim("mulai", struct {
			service.InfoJawaban
			Selesai bool `json:"selesai,omitempty"`
		}{jawaban.Info, jawaban.Ambil(0).Selesai})
	}
	dari := 0
	for {
		k := jawaban.Ambil(dari)
		for i, p := range k.Peristiwa {
			// kode yang sudah diikuti kabar lain sudah dijalankan browser sebelumnya; hanya yang terakhir mungkin masih ditunggu
			if sambung && dari == 0 && p.Jenis == "jalankan_kode" && (i < len(k.Peristiwa)-1 || k.Selesai) {
				continue
			}
			sse.kabar(p.Jenis, p.Data)
		}
		dari += len(k.Peristiwa)
		if k.Selesai {
			if k.Err == nil {
				sse.kirim("selesai", k.Hasil)
			} else if sse.sudahMulai() {
				if !errors.Is(k.Err, context.Canceled) {
					log.Println("error kirim pesan (stream):", k.Err)
				}
				sse.kirim("galat", Response{Status: "gagal", Message: pesanGalatJawaban(k.Err)})
			} else {
				gagalPercakapan(w, k.Err)
			}
			return
		}
		select {
		case <-r.Context().Done():
			return
		case <-k.Baru:
		}
	}
}

// pesanGalatJawaban memilih pesan yang aman untuk jawaban yang gagal setelah stream dimulai
func pesanGalatJawaban(err error) string {
	if errors.Is(err, context.Canceled) {
		return "jawaban dihentikan"
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return "jawaban terlalu lama dan dihentikan"
	}
	return "chatbot sedang bermasalah"
}

// FavoritPesan: PATCH /pesan/{id}/favorit dengan body {"favorit": true}
func FavoritPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Favorit bool `json:"favorit"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 1<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		if err := percakapan.TandaiFavorit(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Favorit); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "favorit diperbarui"})
	}
}

// SematkanPercakapan: PATCH /percakapan/{id}/sematkan dengan body {"sematkan": true}
func SematkanPercakapan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Sematkan bool `json:"sematkan"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 1<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		if err := percakapan.Sematkan(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Sematkan); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "sematan diperbarui"})
	}
}

// NilaiPesan: PATCH /pesan/{id}/penilaian dengan body {"penilaian": 1}; 1 suka, -1 tidak suka, 0 hapus penilaian
func NilaiPesan(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}

		var permintaan struct {
			Penilaian int `json:"penilaian"`
		}
		r.Body = http.MaxBytesReader(w, r.Body, 1<<10)
		if err := json.NewDecoder(r.Body).Decode(&permintaan); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		if err := percakapan.Nilai(id, middleware.PenggunaDari(r.Context()).ID, permintaan.Penilaian); err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "penilaian disimpan"})
	}
}

// DaftarFavorit: GET /pesan/favorit
func DaftarFavorit(percakapan *service.PercakapanService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := percakapan.Favorit(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalPercakapan(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar pesan berbintang", Data: daftar})
	}
}

var polaUUID = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

// bacaID membaca {id} dari alamat; jika bentuknya bukan UUID, langsung membalas 400
func bacaID(w http.ResponseWriter, r *http.Request) (string, bool) {
	id := strings.ToLower(r.PathValue("id"))
	if !polaUUID.MatchString(id) {
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "id tidak valid"})
		return "", false
	}
	return id, true
}

// gagalPercakapan memilih status dan pesan yang aman untuk tiap jenis error
func gagalPercakapan(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, service.ErrPercakapanTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "percakapan tidak ditemukan"})
	case errors.Is(err, service.ErrPesanTidakAda):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: "pesan tidak ditemukan"})
	case errors.Is(err, service.ErrDataTidakValid):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "pertanyaan wajib diisi, maksimal 2000 huruf"})
	case errors.Is(err, service.ErrJudulTidakValid):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "judul wajib diisi, maksimal 100 huruf"})
	case errors.Is(err, service.ErrPenilaianSalah):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "penilaian harus 1, -1, atau 0"})
	case errors.Is(err, service.ErrSedangMenjawab):
		writeJSON(w, http.StatusConflict, Response{Status: "gagal", Message: "percakapan ini masih membuat jawaban, tunggu sampai selesai atau hentikan dulu"})
	case errors.Is(err, service.ErrTerlaluBanyakJawaban):
		writeJSON(w, http.StatusTooManyRequests, Response{Status: "gagal", Message: service.ErrTerlaluBanyakJawaban.Error()})
	case errors.Is(err, context.Canceled), errors.Is(err, context.DeadlineExceeded):
		writeJSON(w, http.StatusConflict, Response{Status: "gagal", Message: pesanGalatJawaban(err)})
	case errors.Is(err, service.ErrAgentGagal):
		// bukan 502: frontend mengulang otomatis 502 sampai 504 (server bangun), sehingga pertanyaan terkirim berkali kali
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "jawaban gagal dibuat, coba lagi"})
	default:
		log.Println("error percakapan:", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
	}
}
