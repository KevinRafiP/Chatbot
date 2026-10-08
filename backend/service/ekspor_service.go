package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"chatbot/backend/repository"
)

type EksporService struct {
	repo        *repository.EksporRepository
	folder      string
	alamat      string
	kunci       string
	driveFolder string
}

func BaruEksporService(repo *repository.EksporRepository, folder, alamat, kunci, driveFolder string) *EksporService {
	return &EksporService{repo: repo, folder: folder, alamat: alamat, kunci: kunci, driveFolder: driveFolder}
}

// Jalankan menulis isi database ke berkas Markdown, lalu mengirimnya bila EKSPOR_URL diisi
func (s *EksporService) Jalankan(ctx context.Context) (lokasi string, terkirim bool, err error) {
	sekarang := time.Now()
	isi, err := s.susun(sekarang)
	if err != nil {
		return "", false, err
	}

	nama := "ekspor-" + sekarang.Format("20060102-150405") + ".md"
	if err := os.MkdirAll(s.folder, 0o700); err != nil {
		return "", false, err
	}
	lokasi = filepath.Join(s.folder, nama)
	if err := os.WriteFile(lokasi, []byte(isi), 0o600); err != nil {
		return "", false, err
	}

	if s.alamat == "" {
		return lokasi, false, nil
	}
	if err := s.kirim(ctx, nama, isi); err != nil {
		return lokasi, false, err
	}
	return lokasi, true, nil
}

// susun mengubah setiap tabel menjadi satu bagian berisi tabel Markdown
func (s *EksporService) susun(waktu time.Time) (string, error) {
	var b strings.Builder
	fmt.Fprintf(&b, "# Ekspor database\n\nDibuat: %s\n", waktu.Format("2006-01-02 15:04:05 MST"))

	for _, tabel := range repository.DaftarTabelEkspor {
		baris, err := s.repo.Baris(tabel)
		if err != nil {
			return "", fmt.Errorf("tabel %s: %w", tabel.Nama, err)
		}

		fmt.Fprintf(&b, "\n## %s (%d baris)\n\n", tabel.Nama, len(baris))
		b.WriteString("| " + strings.Join(tabel.Kolom, " | ") + " |\n")
		b.WriteString("|" + strings.Repeat(" --- |", len(tabel.Kolom)) + "\n")
		for _, nilai := range baris {
			for i := range nilai {
				nilai[i] = rapikanSel(nilai[i])
			}
			b.WriteString("| " + strings.Join(nilai, " | ") + " |\n")
		}
	}
	return b.String(), nil
}

// rapikanSel menjaga isi satu sel tetap di satu baris dan tidak merusak garis tabel
func rapikanSel(teks string) string {
	teks = strings.Join(strings.Fields(teks), " ")
	return strings.ReplaceAll(teks, "|", "\\|")
}

// kirim mengirim berkas sebagai JSON ke EKSPOR_URL (misalnya Apps Script yang menyimpan ke Google Drive)
func (s *EksporService) kirim(ctx context.Context, nama, isi string) error {
	badan, err := json.Marshal(map[string]string{
		"kunci":  s.kunci,
		"folder": s.driveFolder,
		"nama":   nama,
		"isi":    isi,
	})
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.alamat, bytes.NewReader(badan))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	klien := &http.Client{Timeout: 60 * time.Second}
	resp, err := klien.Do(req)
	if err != nil {
		return fmt.Errorf("tujuan ekspor tidak bisa dihubungi: %w", err)
	}
	defer resp.Body.Close()

	var balasan struct {
		Status  string `json:"status"`
		Message string `json:"message"`
	}
	mentah, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode != http.StatusOK || json.Unmarshal(mentah, &balasan) != nil || balasan.Status != "sukses" {
		return fmt.Errorf("tujuan ekspor menolak (status %d): %s", resp.StatusCode, potong(balasan.Message+" "+string(mentah), 200))
	}
	return nil
}
