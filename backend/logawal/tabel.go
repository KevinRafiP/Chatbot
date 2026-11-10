// Package logawal menyusun keterangan saat layanan menyala menjadi satu tabel rapi di terminal
package logawal

import (
	"fmt"
	"log"
	"strings"
	"time"
)

const lebarGaris = 64

// Tabel adalah daftar baris "label : nilai" yang dicetak sekaligus
type Tabel struct {
	judul string
	baris [][2]string
}

func Baru(judul string) *Tabel {
	return &Tabel{judul: judul}
}

// Isi menambah satu baris
func (t *Tabel) Isi(label, nilai string) {
	t.baris = append(t.baris, [2]string{label, nilai})
}

// Ganti mengubah nilai baris yang labelnya sama, misalnya keterangan yang baru diketahui belakangan;
// bila belum ada, baris ditambah di akhir
func (t *Tabel) Ganti(label, nilai string) {
	for i := range t.baris {
		if t.baris[i][0] == label {
			t.baris[i][1] = nilai
			return
		}
	}
	t.Isi(label, nilai)
}

// Isif sama seperti Isi, nilainya disusun seperti fmt.Sprintf
func (t *Tabel) Isif(label, format string, a ...any) {
	t.Isi(label, fmt.Sprintf(format, a...))
}

// Cetak menulis seluruh tabel dalam satu kali tulis, agar tidak tersela log lain
func (t *Tabel) Cetak() {
	panjang := 0
	for _, b := range t.baris {
		panjang = max(panjang, len([]rune(b[0])))
	}
	var s strings.Builder
	garis, pemisah := strings.Repeat("=", lebarGaris), strings.Repeat("-", lebarGaris)
	fmt.Fprintf(&s, "\n%s\n  %s\n%s\n", garis, strings.ToUpper(t.judul), pemisah)
	for _, b := range t.baris {
		fmt.Fprintf(&s, "  %-*s : %s\n", panjang, b[0], b[1])
	}
	fmt.Fprintf(&s, "%s\n", garis)
	log.Writer().Write([]byte(s.String()))
}

// Durasi menulis lama waktu dengan kata, misalnya "24 jam" atau "30 menit"
func Durasi(d time.Duration) string {
	switch {
	case d >= time.Hour && d%time.Hour == 0:
		return fmt.Sprintf("%d jam", d/time.Hour)
	case d >= time.Minute && d%time.Minute == 0:
		return fmt.Sprintf("%d menit", d/time.Minute)
	}
	return d.String()
}

// AktifMati menulis "aktif" atau "mati", ditambah keterangan bila ada
func AktifMati(aktif bool, keterangan string) string {
	kata := "mati"
	if aktif {
		kata = "aktif"
	}
	if keterangan == "" {
		return kata
	}
	return kata + ", " + keterangan
}
