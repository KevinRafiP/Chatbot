package handler

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"

	"chatbot/backend/service"
)

// IngestSatu: POST /ingestion/pengetahuan dengan body satu data
func IngestSatu(ingestion *service.IngestionService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var data service.DataMasuk
		if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body JSON tidak valid"})
			return
		}

		hasil, err := ingestion.Simpan(data)
		if errors.Is(err, service.ErrDataTidakValid) {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: err.Error()})
			return
		}
		if err != nil {
			log.Println("error ingestion:", err)
			writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "gagal menyimpan data"})
			return
		}
		writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "data tersimpan", Data: hasil})
	}
}

// IngestBanyak: POST /ingestion/pengetahuan/batch dengan body daftar data
func IngestBanyak(ingestion *service.IngestionService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var daftar []service.DataMasuk
		if err := json.NewDecoder(r.Body).Decode(&daftar); err != nil {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "body harus berupa daftar JSON [ {...}, {...} ]"})
			return
		}
		if len(daftar) == 0 {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "daftar data kosong"})
			return
		}
		if len(daftar) > service.BatasBatch {
			pesan := fmt.Sprintf("maksimal %d data per kiriman", service.BatasBatch)
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: pesan})
			return
		}

		ringkasan := ingestion.SimpanBanyak(daftar)
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "proses batch selesai", Data: ringkasan})
	}
}
