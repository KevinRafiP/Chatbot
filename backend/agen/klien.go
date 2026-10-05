package agen

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Konteks struct {
	Judul string `json:"judul"`
	Isi   string `json:"isi"`
}

type Sumber struct {
	Judul string `json:"judul"`
	URL   string `json:"url"`
}

type Jawaban struct {
	Jawaban       string   `json:"jawaban"`
	Sumber        []Sumber `json:"sumber"`
	PakaiInternet bool     `json:"pakai_internet"`
}

type Riwayat struct {
	Peran string `json:"peran"`
	Teks  string `json:"teks"`
}

type permintaan struct {
	Pertanyaan string    `json:"pertanyaan"`
	Konteks    []Konteks `json:"konteks"`
	Riwayat    []Riwayat `json:"riwayat"`
}

type balasan struct {
	Status  string  `json:"status"`
	Message string  `json:"message"`
	Data    Jawaban `json:"data"`
}

type Klien struct {
	alamat string
	apiKey string
	http   *http.Client
}

func BaruKlien(alamat, apiKey string) *Klien {
	return &Klien{
		alamat: strings.TrimRight(alamat, "/"),
		apiKey: apiKey,
		http:   &http.Client{Timeout: 90 * time.Second},
	}
}

// Tanya mengirim pertanyaan, data dari database, dan riwayat percakapan ke layanan agent
func (k *Klien) Tanya(ctx context.Context, pertanyaan string, konteks []Konteks, riwayat []Riwayat) (Jawaban, error) {
	badan, err := json.Marshal(permintaan{Pertanyaan: pertanyaan, Konteks: konteks, Riwayat: riwayat})
	if err != nil {
		return Jawaban{}, err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, k.alamat+"/jawab", bytes.NewReader(badan))
	if err != nil {
		return Jawaban{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", k.apiKey)

	resp, err := k.http.Do(req)
	if err != nil {
		return Jawaban{}, fmt.Errorf("agent tidak bisa dihubungi: %w", err)
	}
	defer resp.Body.Close()

	var hasil balasan
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&hasil); err != nil {
		return Jawaban{}, fmt.Errorf("balasan agent tidak valid (status %d): %w", resp.StatusCode, err)
	}
	if resp.StatusCode != http.StatusOK {
		return Jawaban{}, fmt.Errorf("agent menolak (status %d): %s", resp.StatusCode, hasil.Message)
	}
	return hasil.Data, nil
}
