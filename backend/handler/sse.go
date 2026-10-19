package handler

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

// penulisSSE mengirim Server-Sent Events ke browser. Header SSE baru dikirim saat event pertama,
// jadi galat yang terjadi sebelum itu (misalnya percakapan tidak ada) tetap bisa dibalas sebagai JSON biasa
type penulisSSE struct {
	w     http.ResponseWriter
	mulai bool
}

// mintaStream bernilai true jika browser meminta jawaban sebagai Server-Sent Events
func mintaStream(r *http.Request) bool {
	return strings.Contains(r.Header.Get("Accept"), "text/event-stream")
}

// kirim menulis satu event lalu langsung mengirimnya ke browser
func (p *penulisSSE) kirim(jenis string, data any) {
	isi, err := json.Marshal(data)
	if err != nil {
		log.Println("gagal menyusun event SSE:", err)
		return
	}
	if !p.mulai {
		p.mulai = true
		p.w.Header().Set("Content-Type", "text/event-stream")
		p.w.Header().Set("Cache-Control", "no-cache")
		p.w.WriteHeader(http.StatusOK)
	}
	fmt.Fprintf(p.w, "event: %s\ndata: %s\n\n", jenis, isi)
	if f, ok := p.w.(http.Flusher); ok {
		f.Flush()
	}
}

// kabar meneruskan kabar dari agent (status, teks, ulang) apa adanya ke browser
func (p *penulisSSE) kabar(jenis string, data json.RawMessage) {
	p.kirim(jenis, data)
}
