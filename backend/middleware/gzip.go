package middleware

import (
	"compress/gzip"
	"net/http"
	"strings"
	"sync"
)

var poolGzip = sync.Pool{New: func() any { return gzip.NewWriter(nil) }}

// Gzip memampatkan balasan JSON dan teks bila browser mendukungnya, agar bandwidth hemat dan halaman cepat dimuat di HP.
// Stream jawaban (text/event-stream) dan gambar dikirim apa adanya, jadi jawaban tetap mengalir dan gambar tidak dimampatkan dua kali
func Gzip(berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodHead || !strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
			berikutnya.ServeHTTP(w, r)
			return
		}
		w.Header().Add("Vary", "Accept-Encoding")
		p := &penulisGzip{ResponseWriter: w}
		defer p.tutup()
		berikutnya.ServeHTTP(p, r)
	})
}

// penulisGzip baru memutuskan memampatkan atau tidak saat header dikirim, karena Content-Type baru diketahui saat itu
type penulisGzip struct {
	http.ResponseWriter
	gz       *gzip.Writer
	terkirim bool
}

func (p *penulisGzip) WriteHeader(kode int) {
	if p.terkirim {
		return
	}
	p.terkirim = true
	h := p.Header()
	if kode != http.StatusNoContent && kode != http.StatusNotModified && h.Get("Content-Encoding") == "" && bisaDimampatkan(h.Get("Content-Type")) {
		h.Del("Content-Length")
		h.Set("Content-Encoding", "gzip")
		p.gz = poolGzip.Get().(*gzip.Writer)
		p.gz.Reset(p.ResponseWriter)
	}
	p.ResponseWriter.WriteHeader(kode)
}

func (p *penulisGzip) Write(b []byte) (int, error) {
	if !p.terkirim {
		if p.Header().Get("Content-Type") == "" {
			p.Header().Set("Content-Type", http.DetectContentType(b))
		}
		p.WriteHeader(http.StatusOK)
	}
	if p.gz != nil {
		return p.gz.Write(b)
	}
	return p.ResponseWriter.Write(b)
}

// Flush dipakai stream SSE; isi yang dimampatkan juga dikirim saat itu
func (p *penulisGzip) Flush() {
	if p.gz != nil {
		p.gz.Flush()
	}
	if f, ok := p.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func (p *penulisGzip) Unwrap() http.ResponseWriter {
	return p.ResponseWriter
}

func (p *penulisGzip) tutup() {
	if p.gz != nil {
		p.gz.Close()
		poolGzip.Put(p.gz)
		p.gz = nil
	}
}

func bisaDimampatkan(jenis string) bool {
	jenis = strings.ToLower(strings.TrimSpace(strings.Split(jenis, ";")[0]))
	return jenis == "application/json" || (strings.HasPrefix(jenis, "text/") && jenis != "text/event-stream")
}
