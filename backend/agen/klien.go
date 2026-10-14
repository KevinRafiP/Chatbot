package agen

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
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
	Ingatan    string    `json:"ingatan,omitempty"`
}

type permintaanRingkas struct {
	Ingatan string    `json:"ingatan"`
	Riwayat []Riwayat `json:"riwayat"`
}

type hasilRingkas struct {
	Ingatan string `json:"ingatan"`
}

type balasan struct {
	Status  string          `json:"status"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data"`
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

// jedaUlang is the wait before each retry while a sleeping Render service wakes up
var jedaUlang = []time.Duration{5 * time.Second, 10 * time.Second, 20 * time.Second}

// galatSementara marks failures that did not come from the agent itself (network error, or a non-JSON reply from Render)
type galatSementara struct{ error }

// Tanya mengirim pertanyaan, data dari database, riwayat percakapan, dan ingatan tentang pengguna ke layanan agent
func (k *Klien) Tanya(ctx context.Context, pertanyaan string, konteks []Konteks, riwayat []Riwayat, ingatan string) (Jawaban, error) {
	var jawaban Jawaban
	err := k.kirimUlang(ctx, "/jawab", permintaan{Pertanyaan: pertanyaan, Konteks: konteks, Riwayat: riwayat, Ingatan: ingatan}, &jawaban)
	return jawaban, err
}

// Ringkas meminta agent menggabungkan ingatan lama dengan percakapan terbaru menjadi ingatan baru
func (k *Klien) Ringkas(ctx context.Context, ingatan string, riwayat []Riwayat) (string, error) {
	var hasil hasilRingkas
	err := k.kirimUlang(ctx, "/ringkas", permintaanRingkas{Ingatan: ingatan, Riwayat: riwayat}, &hasil)
	return hasil.Ingatan, err
}

// kirimUlang mengirim permintaan ke agent dan mengulang selama agent masih bangun dari tidur
func (k *Klien) kirimUlang(ctx context.Context, jalur string, isi any, tujuan any) error {
	badan, err := json.Marshal(isi)
	if err != nil {
		return err
	}

	for percobaan := 0; ; percobaan++ {
		err := k.kirim(ctx, jalur, badan, tujuan)
		var sementara galatSementara
		if err == nil || !errors.As(err, &sementara) || percobaan >= len(jedaUlang) {
			return err
		}

		log.Printf("agent belum siap, coba lagi dalam %s: %v", jedaUlang[percobaan], err)
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(jedaUlang[percobaan]):
		}
	}
}

func (k *Klien) kirim(ctx context.Context, jalur string, badan []byte, tujuan any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, k.alamat+jalur, bytes.NewReader(badan))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", k.apiKey)

	resp, err := k.http.Do(req)
	if err != nil {
		var galatJaringan net.Error
		if ctx.Err() != nil || (errors.As(err, &galatJaringan) && galatJaringan.Timeout()) {
			return fmt.Errorf("agent tidak bisa dihubungi: %w", err)
		}
		return galatSementara{fmt.Errorf("agent tidak bisa dihubungi: %w", err)}
	}
	defer resp.Body.Close()

	isi, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return galatSementara{fmt.Errorf("gagal membaca balasan agent (status %d): %w", resp.StatusCode, err)}
	}
	var hasil balasan
	if err := json.Unmarshal(isi, &hasil); err != nil {
		return galatSementara{fmt.Errorf("balasan agent bukan JSON (status %d): %.200s", resp.StatusCode, isi)}
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("agent menolak (status %d): %s", resp.StatusCode, hasil.Message)
	}
	return json.Unmarshal(hasil.Data, tujuan)
}
