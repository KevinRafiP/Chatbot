package service

import (
	"errors"
	"sync"
	"time"
)

var ErrTerlaluBanyakGagal = errors.New("terlalu banyak percobaan masuk yang salah, coba lagi beberapa menit lagi")

type catatanGagal struct {
	jumlah int
	mulai  time.Time
}

// pencatatGagal menghitung password salah per email, agar penebak yang berganti-ganti IP tetap tertahan.
// Disimpan di memori, jadi hitungannya kembali nol bila server dijalankan ulang
type pencatatGagal struct {
	mu      sync.Mutex
	maks    int
	jeda    time.Duration
	catatan map[string]*catatanGagal
}

// baruPencatatGagal mengembalikan nil bila maks 0 (mati); semua method aman dipanggil pada nil
func baruPencatatGagal(maks int, jeda time.Duration) *pencatatGagal {
	if maks <= 0 {
		return nil
	}
	return &pencatatGagal{maks: maks, jeda: jeda, catatan: map[string]*catatanGagal{}}
}

// terkunci bernilai true bila email itu sudah salah maks kali dalam jeda terakhir
func (p *pencatatGagal) terkunci(email string) bool {
	if p == nil {
		return false
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	c, ada := p.catatan[email]
	return ada && c.jumlah >= p.maks && time.Since(c.mulai) < p.jeda
}

func (p *pencatatGagal) catat(email string) {
	if p == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	sekarang := time.Now()
	if len(p.catatan) > 10000 {
		for k, c := range p.catatan {
			if sekarang.Sub(c.mulai) >= p.jeda {
				delete(p.catatan, k)
			}
		}
	}
	c, ada := p.catatan[email]
	if !ada || sekarang.Sub(c.mulai) >= p.jeda {
		p.catatan[email] = &catatanGagal{jumlah: 1, mulai: sekarang}
		return
	}
	c.jumlah++
}

func (p *pencatatGagal) hapus(email string) {
	if p == nil {
		return
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.catatan, email)
}
