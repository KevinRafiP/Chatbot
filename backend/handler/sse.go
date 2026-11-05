package handler

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"
)

// JedaJaga adalah jeda tanda "masih hidup" ke browser selama agent belum mengirim apa pun,
// agar proxy di depan Render tidak memutus jawaban yang lama (misalnya model lokal yang lambat)
const JedaJaga = 15 * time.Second

// penulisSSE mengirim Server-Sent Events ke browser. Header SSE baru dikirim saat event pertama,
// jadi galat yang terjadi sebelum itu (misalnya percakapan tidak ada) tetap bisa dibalas sebagai JSON biasa
type penulisSSE struct {
	w     http.ResponseWriter
	mulai bool
	kunci sync.Mutex
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
	p.tulis(fmt.Sprintf("event: %s\ndata: %s\n\n", jenis, isi))
}

// tulis mengirim teks SSE apa adanya; dikunci karena jaga dan kabar agent bisa menulis bersamaan
func (p *penulisSSE) tulis(teks string) {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	if !p.mulai {
		p.mulai = true
		p.w.Header().Set("Content-Type", "text/event-stream")
		p.w.Header().Set("Cache-Control", "no-cache")
		p.w.WriteHeader(http.StatusOK)
	}
	fmt.Fprint(p.w, teks)
	if f, ok := p.w.(http.Flusher); ok {
		f.Flush()
	}
}

// sudahMulai bernilai true jika header SSE sudah terkirim, jadi galat harus dikirim sebagai event
func (p *penulisSSE) sudahMulai() bool {
	p.kunci.Lock()
	defer p.kunci.Unlock()
	return p.mulai
}

// jaga mengirim komentar SSE setiap JedaJaga sampai fungsi yang dikembalikan dipanggil;
// browser mengabaikan komentar, tapi koneksi jadi tidak dianggap diam
func (p *penulisSSE) jaga() func() {
	selesai := make(chan struct{})
	berhenti := make(chan struct{})
	go func() {
		defer close(berhenti)
		detik := time.NewTicker(JedaJaga)
		defer detik.Stop()
		for {
			select {
			case <-selesai:
				return
			case <-detik.C:
				p.tulis(": jaga\n\n")
			}
		}
	}()
	return func() {
		close(selesai)
		<-berhenti
	}
}

// kabar meneruskan kabar dari agent (status, teks, ulang) apa adanya ke browser
func (p *penulisSSE) kabar(jenis string, data json.RawMessage) {
	p.kirim(jenis, data)
}
