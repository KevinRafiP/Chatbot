package pelapor

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"sync"
	"time"
)

const (
	// jedaSama mencegah galat yang sama dikirim berulang kali
	jedaSama    = 10 * time.Minute
	maksPerJam  = 60
	panjangMaks = 4000
)

var (
	polaAngka   = regexp.MustCompile(`[0-9a-f]{8}-[0-9a-f-]{27}|\d+`)
	polaPenting = regexp.MustCompile(`(?i)\b(error|gagal|panic|fatal)\b`)
)

// Sentry mengirim galat ke Sentry lewat API "envelope" tanpa SDK, jadi tidak menambah dependensi
type Sentry struct {
	alamat     string
	kunci      string
	dsn        string
	host       string
	lingkungan string
	layanan    string
	klien      *http.Client
	mu         sync.Mutex
	terakhir   map[string]time.Time
	jam        time.Time
	jumlahJam  int
}

// Baru mengembalikan nil bila SENTRY_DSN kosong atau salah, jadi laporan galat mati
func Baru(dsn, lingkungan, layanan string) *Sentry {
	alamat, err := url.Parse(strings.TrimSpace(dsn))
	if dsn == "" || err != nil || alamat.User == nil || alamat.Host == "" {
		return nil
	}
	bagian := strings.Split(strings.Trim(alamat.Path, "/"), "/")
	proyek := bagian[len(bagian)-1]
	awalan := strings.Join(bagian[:len(bagian)-1], "/")
	if proyek == "" {
		return nil
	}
	if awalan != "" {
		awalan = "/" + awalan
	}
	if lingkungan == "" {
		lingkungan = "production"
	}
	return &Sentry{
		alamat:     fmt.Sprintf("%s://%s%s/api/%s/envelope/", alamat.Scheme, alamat.Host, awalan, proyek),
		kunci:      alamat.User.Username(),
		dsn:        dsn,
		host:       alamat.Host,
		lingkungan: lingkungan,
		layanan:    layanan,
		klien:      &http.Client{Timeout: 5 * time.Second},
		terakhir:   map[string]time.Time{},
	}
}

// Host dipakai tabel saat menyala, tanpa menampilkan kunci DSN
func (s *Sentry) Host() string {
	return s.host
}

func (s *Sentry) bolehKirim(sidik string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	sekarang := time.Now()
	if sekarang.Sub(s.terakhir[sidik]) < jedaSama {
		return false
	}
	if sekarang.Sub(s.jam) >= time.Hour {
		s.jam, s.jumlahJam = sekarang, 0
		for k, t := range s.terakhir {
			if sekarang.Sub(t) >= jedaSama {
				delete(s.terakhir, k)
			}
		}
	}
	if s.jumlahJam >= maksPerJam {
		return false
	}
	s.jumlahJam++
	s.terakhir[sidik] = sekarang
	return true
}

// Kirim melaporkan satu pesan galat di latar belakang
func (s *Sentry) Kirim(pesan string) {
	if s == nil {
		return
	}
	pesan = strings.TrimSpace(pesan)
	if len(pesan) > panjangMaks {
		pesan = pesan[:panjangMaks]
	}
	sidik := polaAngka.ReplaceAllString(pesan, "#")
	if len(sidik) > 200 {
		sidik = sidik[:200]
	}
	if pesan == "" || !s.bolehKirim(sidik) {
		return
	}
	go s.kirim(pesan, sidik)
}

func (s *Sentry) kirim(pesan, sidik string) {
	acak := make([]byte, 16)
	rand.Read(acak)
	id := hex.EncodeToString(acak)
	waktu := time.Now().UTC().Format(time.RFC3339)
	server, _ := os.Hostname()
	kepala, _ := json.Marshal(map[string]string{"event_id": id, "sent_at": waktu, "dsn": s.dsn})
	isi, _ := json.Marshal(map[string]any{
		"event_id":    id,
		"timestamp":   waktu,
		"platform":    "go",
		"level":       "error",
		"logger":      s.layanan,
		"server_name": server,
		"environment": s.lingkungan,
		"message":     map[string]string{"formatted": pesan},
		"tags":        map[string]string{"layanan": s.layanan},
		"fingerprint": []string{s.layanan, sidik},
	})
	var badan bytes.Buffer
	badan.Write(kepala)
	badan.WriteString("\n{\"type\":\"event\"}\n")
	badan.Write(isi)
	badan.WriteString("\n")

	req, err := http.NewRequest(http.MethodPost, s.alamat, &badan)
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/x-sentry-envelope")
	req.Header.Set("X-Sentry-Auth", "Sentry sentry_version=7, sentry_client=vokapas/1.0, sentry_key="+s.kunci)
	resp, err := s.klien.Do(req)
	if err != nil {
		return
	}
	io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
	resp.Body.Close()
}

// PenulisLog meneruskan log ke tujuan aslinya, dan baris yang berisi error/gagal/panic juga dikirim ke Sentry
func (s *Sentry) PenulisLog(tujuan io.Writer) io.Writer {
	if s == nil {
		return tujuan
	}
	return penulis{tujuan: tujuan, sentry: s}
}

type penulis struct {
	tujuan io.Writer
	sentry *Sentry
}

func (p penulis) Write(b []byte) (int, error) {
	n, err := p.tujuan.Write(b)
	// tabel saat menyala ditulis sekaligus banyak baris, jadi tidak ikut dilaporkan
	if baris := string(b); bytes.Count(b, []byte("\n")) <= 1 && polaPenting.MatchString(baris) {
		p.sentry.Kirim(hapusWaktu(baris))
	}
	return n, err
}

// hapusWaktu membuang tanggal dan jam di awal baris log bawaan Go, contoh "2026/11/11 09:33:00 "
func hapusWaktu(baris string) string {
	if len(baris) > 20 && baris[4] == '/' && baris[7] == '/' && baris[13] == ':' {
		return baris[20:]
	}
	return baris
}
