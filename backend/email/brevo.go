package email

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const alamatBrevo = "https://api.brevo.com/v3/smtp/email"

// KlienBrevo mengirim email lewat API Brevo (HTTPS), karena Render gratis memblokir port SMTP
type KlienBrevo struct {
	apiKey       string
	pengirim     string
	namaPengirim string
	alamat       string
	http         *http.Client
}

func BaruKlienBrevo(apiKey, pengirim, namaPengirim string) *KlienBrevo {
	return &KlienBrevo{
		apiKey:       apiKey,
		pengirim:     pengirim,
		namaPengirim: namaPengirim,
		alamat:       alamatBrevo,
		http:         &http.Client{Timeout: 15 * time.Second},
	}
}

type alamatEmail struct {
	Nama  string `json:"name,omitempty"`
	Email string `json:"email"`
}

type isiBrevo struct {
	Pengirim alamatEmail   `json:"sender"`
	Ke       []alamatEmail `json:"to"`
	Subjek   string        `json:"subject"`
	Teks     string        `json:"textContent"`
}

// Kirim mengirim email teks biasa ke satu alamat
func (k *KlienBrevo) Kirim(ke, subjek, isiTeks string) error {
	body, err := json.Marshal(isiBrevo{
		Pengirim: alamatEmail{Nama: k.namaPengirim, Email: k.pengirim},
		Ke:       []alamatEmail{{Email: ke}},
		Subjek:   subjek,
		Teks:     isiTeks,
	})
	if err != nil {
		return err
	}

	req, err := http.NewRequest(http.MethodPost, k.alamat, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("api-key", k.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := k.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		pesan, _ := io.ReadAll(io.LimitReader(resp.Body, 500))
		return fmt.Errorf("brevo status %d: %s", resp.StatusCode, pesan)
	}
	return nil
}
