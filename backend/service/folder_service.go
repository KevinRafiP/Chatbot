package service

import (
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"unicode/utf8"

	"chatbot/backend/model"
	"chatbot/backend/repository"
)

const (
	// BatasFolder adalah jumlah folder paling banyak per akun
	BatasFolder = 50
	// BatasNamaFolder adalah panjang nama folder, dalam huruf
	BatasNamaFolder = 40
)

var (
	ErrFolderTidakAda    = errors.New("folder tidak ditemukan")
	ErrNamaFolderSalah   = fmt.Errorf("nama folder wajib diisi, maksimal %d huruf", BatasNamaFolder)
	ErrFolderPenuh       = fmt.Errorf("paling banyak %d folder", BatasFolder)
	ErrPindahFolderSalah = errors.New("percakapan atau folder tidak ditemukan")
)

// FolderService mengelola folder untuk mengelompokkan percakapan akun
type FolderService struct {
	repo *repository.FolderRepository
}

func BaruFolderService(repo *repository.FolderRepository) *FolderService {
	return &FolderService{repo: repo}
}

func (s *FolderService) Daftar(penggunaID string) ([]model.Folder, error) {
	return s.repo.Semua(penggunaID)
}

func (s *FolderService) Buat(penggunaID, nama string) (model.Folder, error) {
	nama, err := rapikanNamaFolder(nama)
	if err != nil {
		return model.Folder{}, err
	}
	jumlah, err := s.repo.Jumlah(penggunaID)
	if err != nil {
		return model.Folder{}, err
	}
	if jumlah >= BatasFolder {
		return model.Folder{}, ErrFolderPenuh
	}
	return s.repo.Buat(penggunaID, nama)
}

func (s *FolderService) GantiNama(id, penggunaID, nama string) (model.Folder, error) {
	nama, err := rapikanNamaFolder(nama)
	if err != nil {
		return model.Folder{}, err
	}
	f, err := s.repo.GantiNama(id, penggunaID, nama)
	if errors.Is(err, sql.ErrNoRows) {
		return model.Folder{}, ErrFolderTidakAda
	}
	return f, err
}

func (s *FolderService) Hapus(id, penggunaID string) error {
	ada, err := s.repo.Hapus(id, penggunaID)
	if err != nil {
		return err
	}
	if !ada {
		return ErrFolderTidakAda
	}
	return nil
}

// Pindahkan memasukkan percakapan ke folder; folderID kosong mengeluarkannya dari folder
func (s *FolderService) Pindahkan(percakapanID, penggunaID, folderID string) error {
	ada, err := s.repo.Pindahkan(percakapanID, penggunaID, folderID)
	if err != nil {
		return err
	}
	if !ada {
		return ErrPindahFolderSalah
	}
	return nil
}

func rapikanNamaFolder(nama string) (string, error) {
	nama = strings.Join(strings.Fields(nama), " ")
	if nama == "" || utf8.RuneCountInString(nama) > BatasNamaFolder {
		return "", ErrNamaFolderSalah
	}
	return nama, nil
}
