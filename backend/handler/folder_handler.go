package handler

import (
	"errors"
	"log"
	"net/http"
	"strings"

	"chatbot/backend/middleware"
	"chatbot/backend/service"
)

type permintaanFolder struct {
	Nama string `json:"nama"`
}

// DaftarFolder: GET /folder
func DaftarFolder(folder *service.FolderService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		daftar, err := folder.Daftar(middleware.PenggunaDari(r.Context()).ID)
		if err != nil {
			gagalFolder(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "daftar folder", Data: daftar})
	}
}

// BuatFolder: POST /folder dengan body {"nama": "..."}
func BuatFolder(folder *service.FolderService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var p permintaanFolder
		if !bacaJSON(w, r, &p) {
			return
		}
		baru, err := folder.Buat(middleware.PenggunaDari(r.Context()).ID, p.Nama)
		if err != nil {
			gagalFolder(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, Response{Status: "sukses", Message: "folder dibuat", Data: baru})
	}
}

// GantiNamaFolder: PATCH /folder/{id} dengan body {"nama": "..."}
func GantiNamaFolder(folder *service.FolderService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		var p permintaanFolder
		if !bacaJSON(w, r, &p) {
			return
		}
		hasil, err := folder.GantiNama(id, middleware.PenggunaDari(r.Context()).ID, p.Nama)
		if err != nil {
			gagalFolder(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "nama folder diganti", Data: hasil})
	}
}

// HapusFolder: DELETE /folder/{id}; percakapan di dalamnya tidak ikut terhapus
func HapusFolder(folder *service.FolderService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		if err := folder.Hapus(id, middleware.PenggunaDari(r.Context()).ID); err != nil {
			gagalFolder(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "folder dihapus"})
	}
}

// PindahkanKeFolder: PATCH /percakapan/{id}/folder dengan body {"folder_id": "..."}; folder_id kosong mengeluarkannya
func PindahkanKeFolder(folder *service.FolderService) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, ok := bacaID(w, r)
		if !ok {
			return
		}
		var p struct {
			FolderID string `json:"folder_id"`
		}
		if !bacaJSON(w, r, &p) {
			return
		}
		p.FolderID = strings.ToLower(p.FolderID)
		if p.FolderID != "" && !polaUUID.MatchString(p.FolderID) {
			writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: "id folder tidak valid"})
			return
		}
		if err := folder.Pindahkan(id, middleware.PenggunaDari(r.Context()).ID, p.FolderID); err != nil {
			gagalFolder(w, err)
			return
		}
		writeJSON(w, http.StatusOK, Response{Status: "sukses", Message: "folder percakapan diperbarui"})
	}
}

func gagalFolder(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, service.ErrFolderTidakAda), errors.Is(err, service.ErrPindahFolderSalah):
		writeJSON(w, http.StatusNotFound, Response{Status: "gagal", Message: err.Error()})
	case errors.Is(err, service.ErrNamaFolderSalah), errors.Is(err, service.ErrFolderPenuh):
		writeJSON(w, http.StatusBadRequest, Response{Status: "gagal", Message: err.Error()})
	default:
		log.Println("error folder:", err)
		writeJSON(w, http.StatusInternalServerError, Response{Status: "gagal", Message: "server sedang bermasalah"})
	}
}
