package middleware

import (
	"net/http"
	"sync"
	"time"
)

type hitungan struct {
	jumlah int
	mulai  time.Time
}

type Pembatas struct {
	mu      sync.Mutex
	maks    int
	jendela time.Duration
	catatan map[string]*hitungan
}

// BaruPembatas membuat pembatas: paling banyak maks permintaan per kunci dalam satu jendela waktu
func BaruPembatas(maks int, jendela time.Duration) *Pembatas {
	return &Pembatas{maks: maks, jendela: jendela, catatan: map[string]*hitungan{}}
}

// Izinkan menghitung satu permintaan untuk kunci itu dan menjawab apakah masih di bawah batas
func (p *Pembatas) Izinkan(kunci string) bool {
	p.mu.Lock()
	defer p.mu.Unlock()

	sekarang := time.Now()
	if len(p.catatan) > 1000 {
		for k, h := range p.catatan {
			if sekarang.Sub(h.mulai) >= p.jendela {
				delete(p.catatan, k)
			}
		}
	}

	h, ada := p.catatan[kunci]
	if !ada || sekarang.Sub(h.mulai) >= p.jendela {
		p.catatan[kunci] = &hitungan{jumlah: 1, mulai: sekarang}
		return true
	}
	if h.jumlah >= p.maks {
		return false
	}
	h.jumlah++
	return true
}

// BatasiLaju menolak dengan status 429 bila kunci dari request itu sudah melewati batas
func BatasiLaju(p *Pembatas, kunci func(r *http.Request) string, berikutnya http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !p.Izinkan(kunci(r)) {
			tolak(w, http.StatusTooManyRequests, "terlalu banyak permintaan, coba lagi nanti")
			return
		}
		berikutnya.ServeHTTP(w, r)
	})
}
