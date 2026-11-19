package service

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"strings"
	"syscall"
	"time"
)

// MaksByteGambar sama dengan batas agent saat memeriksa gambar
const MaksByteGambar = 3_000_000

// agen pengguna yang sama dengan agent (gambar_web.agen_gambar), agar situs yang lolos dicek agent juga mau dibuka di sini
const agenPenggunaGambar = "Mozilla/5.0 (compatible; Vokapas/1.0)"

// aturan agen pengguna Wikimedia juga berlaku untuk berkas gambarnya, jadi di sana kontak WIKI_KONTAK ikut dikirim
var situsWikimedia = []string{"wikimedia.org", "wikipedia.org"}

var ErrGambarTidakAda = errors.New("gambar tidak tersedia")

var jenisGambar = map[string]string{"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}

// alamat yang bukan internet umum walau lolos IsPrivate: CGNAT, jaringan uji, dan alamat khusus IANA
var jaringanTerlarang = []netip.Prefix{
	netip.MustParsePrefix("100.64.0.0/10"),
	netip.MustParsePrefix("192.0.0.0/24"),
	netip.MustParsePrefix("198.18.0.0/15"),
}

// PenerusGambar meneruskan gambar dari internet ke browser tanpa menyimpannya, hanya untuk alamat yang ditandatangani backend
type PenerusGambar struct {
	kunci    []byte
	klien    *http.Client
	agenWiki string
}

// BaruPenerusGambar memakai AGENT_API_KEY sebagai bahan kunci tanda; jika kosong kuncinya acak,
// sehingga tanda gambar lama tidak berlaku lagi setelah backend dinyalakan ulang
func BaruPenerusGambar(rahasia, kontakWiki string) *PenerusGambar {
	kunci := sha256.Sum256([]byte("gambar|" + rahasia))
	if rahasia == "" {
		rand.Read(kunci[:])
	}
	dialer := &net.Dialer{Timeout: 5 * time.Second, Control: tolakAlamatInternal}
	transport := &http.Transport{
		DialContext:           dialer.DialContext,
		TLSHandshakeTimeout:   5 * time.Second,
		ResponseHeaderTimeout: 8 * time.Second,
		MaxIdleConns:          20,
		IdleConnTimeout:       60 * time.Second,
	}
	klien := &http.Client{
		Transport: transport,
		Timeout:   20 * time.Second,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= 3 || (req.URL.Scheme != "http" && req.URL.Scheme != "https") {
				return ErrGambarTidakAda
			}
			return nil
		},
	}
	agenWiki := agenPenggunaGambar
	if kontakWiki != "" {
		agenWiki = "Vokapas/1.0 (" + kontakWiki + ")"
	}
	return &PenerusGambar{kunci: kunci[:], klien: klien, agenWiki: agenWiki}
}

func (p *PenerusGambar) agenPengguna(host string) string {
	host = strings.ToLower(host)
	for _, situs := range situsWikimedia {
		if host == situs || strings.HasSuffix(host, "."+situs) {
			return p.agenWiki
		}
	}
	return agenPenggunaGambar
}

// Tanda dikirim bersama alamat gambar di setiap pesan, agar /gambar tidak bisa dipakai sebagai proxy untuk alamat lain
func (p *PenerusGambar) Tanda(alamat string) string {
	m := hmac.New(sha256.New, p.kunci)
	m.Write([]byte(alamat))
	return hex.EncodeToString(m.Sum(nil)[:16])
}

func (p *PenerusGambar) Cocok(alamat, tanda string) bool {
	return hmac.Equal([]byte(p.Tanda(alamat)), []byte(tanda))
}

// Ambil membuka gambar dari situs asal dan mengembalikan isinya beserta jenisnya (dibaca dari byte awal, bukan dari header situs);
// pemanggil wajib menutup isinya. Isinya dipotong di MaksByteGambar
func (p *PenerusGambar) Ambil(ctx context.Context, alamat string) (io.ReadCloser, string, error) {
	u, err := url.Parse(alamat)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil {
		return nil, "", ErrGambarTidakAda
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, alamat, nil)
	if err != nil {
		return nil, "", ErrGambarTidakAda
	}
	req.Header.Set("User-Agent", p.agenPengguna(u.Hostname()))
	req.Header.Set("Accept", "image/*")
	resp, err := p.klien.Do(req)
	if err != nil {
		return nil, "", ErrGambarTidakAda
	}
	if resp.StatusCode != http.StatusOK || resp.ContentLength > MaksByteGambar {
		resp.Body.Close()
		return nil, "", ErrGambarTidakAda
	}
	awal := make([]byte, 512)
	n, _ := io.ReadFull(resp.Body, awal)
	jenis := http.DetectContentType(awal[:n])
	if _, ok := jenisGambar[jenis]; !ok {
		resp.Body.Close()
		return nil, "", ErrGambarTidakAda
	}
	isi := io.MultiReader(bytes.NewReader(awal[:n]), io.LimitReader(resp.Body, int64(MaksByteGambar-n)))
	return struct {
		io.Reader
		io.Closer
	}{isi, resp.Body}, jenis, nil
}

// EkstensiGambar dipakai untuk nama berkas saat gambar diunduh
func EkstensiGambar(jenis string) string {
	return jenisGambar[jenis]
}

// tolakAlamatInternal dicek pada alamat IP yang benar-benar dihubungi, jadi pengalihan atau DNS yang berubah
// tetap tidak bisa membuka jaringan internal server
func tolakAlamatInternal(_, alamat string, _ syscall.RawConn) error {
	host, port, err := net.SplitHostPort(alamat)
	if err != nil || (port != "80" && port != "443") {
		return ErrGambarTidakAda
	}
	ip, err := netip.ParseAddr(host)
	if err != nil {
		return ErrGambarTidakAda
	}
	ip = ip.Unmap()
	if !ip.IsGlobalUnicast() || ip.IsPrivate() {
		return ErrGambarTidakAda
	}
	for _, jaringan := range jaringanTerlarang {
		if jaringan.Contains(ip) {
			return ErrGambarTidakAda
		}
	}
	return nil
}
