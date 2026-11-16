package service

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"chatbot/backend/model"
)

const (
	alamatMasukGoogle = "https://accounts.google.com/o/oauth2/v2/auth"
	alamatTokenGoogle = "https://oauth2.googleapis.com/token"
	// masaTungguGoogle adalah waktu pengguna untuk memilih akun di halaman Google
	masaTungguGoogle = 10 * time.Minute
	// masaKodeGoogle adalah umur kode sekali pakai yang dibawa frontend untuk ditukar dengan sesi
	masaKodeGoogle   = 2 * time.Minute
	maksTungguGoogle = 10000
)

var ErrKodeGoogleSalah = errors.New("kode masuk Google tidak valid atau sudah kedaluwarsa, coba masuk lagi")

type tungguGoogle struct {
	verifier  string
	tokenTamu string
	perangkat string
	ingat     bool
	sampai    time.Time
}

type sesiGoogle struct {
	token    string
	ingat    bool
	pengguna model.Pengguna
	sampai   time.Time
}

// MasukGoogle menjalankan "Masuk dengan Google" (OAuth 2.0 authorization code + PKCE). Browser dibawa ke Google,
// Google mengembalikannya ke backend, lalu backend mengarahkan ke frontend dengan kode sekali pakai, bukan token sesi,
// agar token tidak pernah muncul di alamat halaman
type MasukGoogle struct {
	clientID       string
	rahasia        string
	alamatKembali  string
	alamatFrontend string
	akun           *AkunService
	klien          *http.Client
	alamatToken    string
	mu             sync.Mutex
	tunggu         map[string]tungguGoogle
	kode           map[string]sesiGoogle
}

// BaruMasukGoogle mengembalikan nil bila GOOGLE_CLIENT_ID atau GOOGLE_CLIENT_SECRET kosong; tombol Google lalu disembunyikan
func BaruMasukGoogle(clientID, rahasia, alamatKembali, alamatFrontend string, akun *AkunService) *MasukGoogle {
	if clientID == "" || rahasia == "" {
		return nil
	}
	return &MasukGoogle{clientID: clientID, rahasia: rahasia, alamatKembali: alamatKembali,
		alamatFrontend: strings.TrimRight(alamatFrontend, "/"), akun: akun, klien: &http.Client{Timeout: 15 * time.Second},
		alamatToken: alamatTokenGoogle, tunggu: map[string]tungguGoogle{}, kode: map[string]sesiGoogle{}}
}

// AlamatKembali adalah alamat yang harus didaftarkan di Google Cloud Console sebagai "Authorized redirect URI"
func (g *MasukGoogle) AlamatKembali() string {
	return g.alamatKembali
}

// Mulai membuat alamat halaman masuk Google; tokenTamu dipakai untuk memindahkan percakapan tamu ke akun
func (g *MasukGoogle) Mulai(tokenTamu, perangkat string, ingat bool) (string, error) {
	state, err := tokenBaru()
	if err != nil {
		return "", err
	}
	verifier, err := tokenBaru()
	if err != nil {
		return "", err
	}
	g.mu.Lock()
	g.buangKedaluwarsa()
	if len(g.tunggu) >= maksTungguGoogle {
		g.mu.Unlock()
		return "", errors.New("terlalu banyak permintaan masuk Google yang menunggu")
	}
	g.tunggu[state] = tungguGoogle{verifier: verifier, tokenTamu: tokenTamu, perangkat: perangkat, ingat: ingat,
		sampai: time.Now().Add(masaTungguGoogle)}
	g.mu.Unlock()

	tantangan := sha256.Sum256([]byte(verifier))
	q := url.Values{
		"client_id":             {g.clientID},
		"redirect_uri":          {g.alamatKembali},
		"response_type":         {"code"},
		"scope":                 {"openid email profile"},
		"state":                 {state},
		"code_challenge":        {base64.RawURLEncoding.EncodeToString(tantangan[:])},
		"code_challenge_method": {"S256"},
		"prompt":                {"select_account"},
	}
	return alamatMasukGoogle + "?" + q.Encode(), nil
}

// Kembali menyelesaikan masuk setelah Google mengarahkan browser ke backend, lalu mengembalikan alamat frontend:
// ?masuk_google=<kode> bila berhasil, atau ?google_gagal=<alasan> (batal, kedaluwarsa, email, gagal)
func (g *MasukGoogle) Kembali(ctx context.Context, state, kode, galat string) string {
	g.mu.Lock()
	t, ada := g.tunggu[state]
	delete(g.tunggu, state)
	g.mu.Unlock()
	switch {
	case galat == "access_denied":
		return g.keFrontend("google_gagal", "batal")
	case !ada || time.Now().After(t.sampai):
		return g.keFrontend("google_gagal", "kedaluwarsa")
	case galat != "" || kode == "":
		return g.keFrontend("google_gagal", "gagal")
	}

	klaim, err := g.tukarKode(ctx, kode, t.verifier)
	if err != nil {
		log.Println("gagal menukar kode Google:", err)
		return g.keFrontend("google_gagal", "gagal")
	}
	if !klaim.EmailTerverifikasi || klaim.Email == "" {
		return g.keFrontend("google_gagal", "email")
	}
	token, pengguna, err := g.akun.MasukGoogle(klaim.Sub, klaim.Email, klaim.Nama, t.tokenTamu, t.perangkat, t.ingat)
	if err != nil {
		log.Println("gagal masuk dengan Google:", err)
		return g.keFrontend("google_gagal", "gagal")
	}
	sekali, err := tokenBaru()
	if err != nil {
		log.Println("gagal membuat kode masuk Google:", err)
		return g.keFrontend("google_gagal", "gagal")
	}
	g.mu.Lock()
	g.kode[sekali] = sesiGoogle{token: token, ingat: t.ingat, pengguna: pengguna, sampai: time.Now().Add(masaKodeGoogle)}
	g.mu.Unlock()
	return g.keFrontend("masuk_google", sekali)
}

// Tukar memberikan token sesi untuk kode sekali pakai dari Kembali
func (g *MasukGoogle) Tukar(kode string) (string, bool, model.Pengguna, error) {
	g.mu.Lock()
	s, ada := g.kode[kode]
	delete(g.kode, kode)
	g.mu.Unlock()
	if !ada || time.Now().After(s.sampai) {
		return "", false, model.Pengguna{}, ErrKodeGoogleSalah
	}
	return s.token, s.ingat, s.pengguna, nil
}

type klaimGoogle struct {
	Iss                string `json:"iss"`
	Aud                string `json:"aud"`
	Sub                string `json:"sub"`
	Email              string `json:"email"`
	EmailTerverifikasi bool   `json:"email_verified"`
	Nama               string `json:"name"`
	Exp                int64  `json:"exp"`
}

// tukarKode menukar kode dari Google dengan id_token. Token diterima langsung dari Google lewat HTTPS dengan client secret,
// jadi isinya bisa dipercaya tanpa memeriksa tanda tangan; penerima, penerbit, dan masa berlakunya tetap dicek
func (g *MasukGoogle) tukarKode(ctx context.Context, kode, verifier string) (klaimGoogle, error) {
	badan := url.Values{
		"code":          {kode},
		"client_id":     {g.clientID},
		"client_secret": {g.rahasia},
		"redirect_uri":  {g.alamatKembali},
		"grant_type":    {"authorization_code"},
		"code_verifier": {verifier},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, g.alamatToken, strings.NewReader(badan.Encode()))
	if err != nil {
		return klaimGoogle{}, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := g.klien.Do(req)
	if err != nil {
		return klaimGoogle{}, err
	}
	defer resp.Body.Close()
	var hasil struct {
		IDToken string `json:"id_token"`
		Galat   string `json:"error"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 64<<10)).Decode(&hasil); err != nil {
		return klaimGoogle{}, err
	}
	if resp.StatusCode != http.StatusOK || hasil.IDToken == "" {
		return klaimGoogle{}, fmt.Errorf("status %d: %s", resp.StatusCode, hasil.Galat)
	}

	bagian := strings.Split(hasil.IDToken, ".")
	if len(bagian) != 3 {
		return klaimGoogle{}, errors.New("id_token tidak valid")
	}
	isi, err := base64.RawURLEncoding.DecodeString(bagian[1])
	if err != nil {
		return klaimGoogle{}, err
	}
	var klaim klaimGoogle
	if err := json.Unmarshal(isi, &klaim); err != nil {
		return klaimGoogle{}, err
	}
	if klaim.Aud != g.clientID || (klaim.Iss != "accounts.google.com" && klaim.Iss != "https://accounts.google.com") ||
		time.Now().Unix() > klaim.Exp || klaim.Sub == "" {
		return klaimGoogle{}, errors.New("id_token bukan untuk aplikasi ini atau sudah kedaluwarsa")
	}
	return klaim, nil
}

func (g *MasukGoogle) keFrontend(kunci, nilai string) string {
	return g.alamatFrontend + "/?" + url.Values{kunci: {nilai}}.Encode()
}

// buangKedaluwarsa dipanggil dengan mu terkunci
func (g *MasukGoogle) buangKedaluwarsa() {
	sekarang := time.Now()
	for k, t := range g.tunggu {
		if sekarang.After(t.sampai) {
			delete(g.tunggu, k)
		}
	}
	for k, s := range g.kode {
		if sekarang.After(s.sampai) {
			delete(g.kode, k)
		}
	}
}
