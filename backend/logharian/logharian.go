// Package logharian menulis log ke satu berkas per tanggal di folder log/ proyek (misalnya log/2026-11-20.log) yang dipakai
// bersama agent, setiap baris diawali nama bagiannya, sambil tetap tampil di terminal; hanya di lokal, karena Render selalu mengisi variabel RENDER
package logharian

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

var garis = strings.Repeat("=", 100)

type penulis struct {
	mu      sync.Mutex
	folder  string
	label   string
	tanggal string
	berkas  *os.File
}

// Write membuka berkas baru saat tanggal berganti; gagal menulis berkas tidak boleh menghentikan log di terminal
func (p *penulis) Write(b []byte) (int, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	tanggal := time.Now().Format("2006-01-02")
	if tanggal != p.tanggal {
		if p.berkas != nil {
			p.berkas.Close()
		}
		berkas, err := os.OpenFile(filepath.Join(p.folder, tanggal+".log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
		if err != nil {
			p.berkas, p.tanggal = nil, ""
			return len(b), nil
		}
		p.berkas, p.tanggal = berkas, tanggal
	}
	var isi strings.Builder
	for _, baris := range strings.SplitAfter(string(b), "\n") {
		if baris != "" {
			isi.WriteString(p.label + baris)
		}
	}
	p.berkas.WriteString(isi.String())
	return len(b), nil
}

// Pasang menambah berkas harian ke tujuan log standar dan mengembalikan keterangan untuk tabel awal
func Pasang(nama string) string {
	if os.Getenv("RENDER") != "" {
		return "mati di Render"
	}
	folder := filepath.Join(akarProyek(), "log")
	if err := os.MkdirAll(folder, 0o755); err != nil {
		return "mati, folder log tidak bisa dibuat: " + err.Error()
	}
	p := &penulis{folder: folder, label: fmt.Sprintf("%-13s | ", nama)}
	log.SetOutput(io.MultiWriter(log.Writer(), p))
	fmt.Fprintf(p, "\n%s\n%s MENYALA %s\n%s\n", garis, strings.ToUpper(nama), time.Now().Format("2006-01-02 15:04:05"), garis)
	return "aktif, " + filepath.Join(folder, "<tanggal>.log")
}

// akarProyek adalah folder di atas go.mod, jadi log backend berada di folder log/ yang sama dengan log agent
func akarProyek() string {
	awal, err := os.Getwd()
	if err != nil {
		return "."
	}
	for folder := awal; ; folder = filepath.Dir(folder) {
		if _, err := os.Stat(filepath.Join(folder, "go.mod")); err == nil {
			return filepath.Dir(folder)
		}
		if filepath.Dir(folder) == folder {
			return awal
		}
	}
}
