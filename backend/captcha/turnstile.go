package captcha

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// AlamatTurnstile adalah alamat pemeriksaan token Cloudflare Turnstile; bisa diganti lewat TURNSTILE_URL
const AlamatTurnstile = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

var (
	ErrTokenKosong  = errors.New("verifikasi keamanan belum selesai, coba lagi")
	ErrTokenDitolak = errors.New("verifikasi keamanan gagal, muat ulang halaman lalu coba lagi")
)

// Turnstile memeriksa token captcha Cloudflare Turnstile yang dikirim browser
type Turnstile struct {
	rahasia string
	alamat  string
	klien   *http.Client
}

// BaruTurnstile mengembalikan nil bila rahasia kosong, artinya captcha mati
func BaruTurnstile(rahasia, alamat string) *Turnstile {
	if rahasia == "" {
		return nil
	}
	if alamat == "" {
		alamat = AlamatTurnstile
	}
	return &Turnstile{rahasia: rahasia, alamat: alamat, klien: &http.Client{Timeout: 10 * time.Second}}
}

// Periksa menanyakan ke Cloudflare apakah token itu sah dan belum pernah dipakai.
// Bila Cloudflare tidak bisa dihubungi, permintaan ditolak (lebih aman daripada meloloskan bot)
func (t *Turnstile) Periksa(ctx context.Context, token, ip string) error {
	token = strings.TrimSpace(token)
	if token == "" || len(token) > 2048 {
		return ErrTokenKosong
	}
	data := url.Values{"secret": {t.rahasia}, "response": {token}}
	if ip != "" {
		data.Set("remoteip", ip)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, t.alamat, strings.NewReader(data.Encode()))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	res, err := t.klien.Do(req)
	if err != nil {
		return ErrTokenDitolak
	}
	defer res.Body.Close()

	var hasil struct {
		Success bool `json:"success"`
	}
	if res.StatusCode != http.StatusOK || json.NewDecoder(res.Body).Decode(&hasil) != nil || !hasil.Success {
		return ErrTokenDitolak
	}
	return nil
}
