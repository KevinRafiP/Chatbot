package agen

import (
	"bufio"
	"bytes"
	"context"
	"encoding/base64"
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
	Email         *Email   `json:"email,omitempty"`
}

// Email adalah isi email yang diminta pengguna lewat alat kirim_email; dikirim backend setelah jawaban selesai
type Email struct {
	Subjek string `json:"subjek"`
	Isi    string `json:"isi"`
}

// Lampiran adalah teks dari berkas yang diunggah pengguna
type Lampiran struct {
	Nama string `json:"nama"`
	Teks string `json:"teks"`
}

// Tambahan berisi data pilihan untuk satu pertanyaan: lampiran berkas dan izin mengirim email
type Tambahan struct {
	Lampiran  *Lampiran
	BisaEmail bool
}

// Berkas adalah hasil membaca berkas unggahan di agent
type Berkas struct {
	Nama        string `json:"nama"`
	Teks        string `json:"teks"`
	JumlahHuruf int    `json:"jumlah_huruf"`
	Terpotong   bool   `json:"terpotong"`
	Halaman     *int   `json:"halaman"`
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
	Profil     string    `json:"profil"`
	Lampiran   *Lampiran `json:"lampiran,omitempty"`
	BisaEmail  bool      `json:"bisa_email,omitempty"`
}

type permintaanBerkas struct {
	Nama string `json:"nama"`
	Isi  string `json:"isi"`
}

// Profil agent: tamu paling hemat, cepat untuk jawaban singkat, mendalam untuk pemikiran yang lebih kompleks
const (
	ProfilTamu     = "tamu"
	ProfilCepat    = "cepat"
	ProfilMendalam = "mendalam"
)

type permintaanRingkas struct {
	Ingatan string    `json:"ingatan"`
	Riwayat []Riwayat `json:"riwayat"`
}

// Jenis teks untuk embedding: dokumen untuk data yang disimpan, kueri untuk pertanyaan pengguna
const (
	EmbedDokumen = "dokumen"
	EmbedKueri   = "kueri"
)

type permintaanEmbed struct {
	Teks  []string `json:"teks"`
	Jenis string   `json:"jenis"`
}

type hasilEmbed struct {
	Model  string      `json:"model"`
	Vektor [][]float32 `json:"vektor"`
}

// InfoEmbed adalah pengaturan embedding yang sedang aktif di agent
type InfoEmbed struct {
	Aktif       bool    `json:"aktif"`
	Model       string  `json:"model"`
	SkorMinimal float64 `json:"skor_minimal"`
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
	stream *http.Client
}

// BatasWaktuStream adalah waktu paling lama satu jawaban stream; client stream tidak memakai Timeout
// karena Timeout ikut memotong body yang masih mengalir
const BatasWaktuStream = 3 * time.Minute

// Kabar menerima kabar dari agent selama jawaban dibuat: jenis "status", "teks", atau "ulang"
type Kabar func(jenis string, data json.RawMessage)

func BaruKlien(alamat, apiKey string) *Klien {
	return &Klien{
		alamat: strings.TrimRight(alamat, "/"),
		apiKey: apiKey,
		http:   &http.Client{Timeout: 90 * time.Second},
		stream: &http.Client{},
	}
}

// jedaUlang is the wait before each retry while a sleeping Render service wakes up
var jedaUlang = []time.Duration{5 * time.Second, 10 * time.Second, 20 * time.Second}

// GalatDitolak adalah penolakan dari agent; Pesan aman ditampilkan ke pengguna bila Status 400
type GalatDitolak struct {
	Status int
	Pesan  string
}

func (g GalatDitolak) Error() string {
	return fmt.Sprintf("agent menolak (status %d): %s", g.Status, g.Pesan)
}

// galatSementara marks failures that did not come from the agent itself (network error, or a non-JSON reply from Render)
type galatSementara struct{ error }

// Tanya mengirim pertanyaan, data dari database, riwayat percakapan, dan ingatan tentang pengguna ke layanan agent;
// profil menentukan kemampuan agent: ProfilTamu, ProfilCepat, atau ProfilMendalam
func (k *Klien) Tanya(ctx context.Context, pertanyaan string, konteks []Konteks, riwayat []Riwayat, ingatan, profil string, tambahan Tambahan) (Jawaban, error) {
	var jawaban Jawaban
	err := k.kirimUlang(ctx, "/jawab", permintaan{Pertanyaan: pertanyaan, Konteks: konteks, Riwayat: riwayat, Ingatan: ingatan, Profil: profil,
		Lampiran: tambahan.Lampiran, BisaEmail: tambahan.BisaEmail}, &jawaban)
	return jawaban, err
}

// TanyaStream sama seperti Tanya, tetapi jawaban diterima sebagai Server-Sent Events;
// setiap status dan potongan teks diteruskan ke kabar, lalu hasil akhirnya dikembalikan
func (k *Klien) TanyaStream(ctx context.Context, pertanyaan string, konteks []Konteks, riwayat []Riwayat, ingatan, profil string, tambahan Tambahan, kabar Kabar) (Jawaban, error) {
	badan, err := json.Marshal(permintaan{Pertanyaan: pertanyaan, Konteks: konteks, Riwayat: riwayat, Ingatan: ingatan, Profil: profil,
		Lampiran: tambahan.Lampiran, BisaEmail: tambahan.BisaEmail})
	if err != nil {
		return Jawaban{}, err
	}
	ctx, batal := context.WithTimeout(ctx, BatasWaktuStream)
	defer batal()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, k.alamat+"/jawab-stream", bytes.NewReader(badan))
	if err != nil {
		return Jawaban{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", k.apiKey)

	resp, err := k.stream.Do(req)
	if err != nil {
		return Jawaban{}, fmt.Errorf("agent tidak bisa dihubungi: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		isi, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<10))
		return Jawaban{}, fmt.Errorf("agent menolak stream (status %d): %.200s", resp.StatusCode, isi)
	}

	pembaca := bufio.NewScanner(resp.Body)
	pembaca.Buffer(make([]byte, 64<<10), 1<<20)
	jenis := ""
	for pembaca.Scan() {
		baris := pembaca.Text()
		if nama, ok := strings.CutPrefix(baris, "event: "); ok {
			jenis = nama
			continue
		}
		isi, ok := strings.CutPrefix(baris, "data: ")
		if !ok {
			continue
		}
		switch jenis {
		case "selesai":
			var jawaban Jawaban
			return jawaban, json.Unmarshal([]byte(isi), &jawaban)
		case "galat":
			var galat struct {
				Message string `json:"message"`
			}
			json.Unmarshal([]byte(isi), &galat)
			return Jawaban{}, fmt.Errorf("agent gagal: %s", galat.Message)
		default:
			kabar(jenis, json.RawMessage(isi))
		}
	}
	if err := pembaca.Err(); err != nil {
		return Jawaban{}, fmt.Errorf("stream agent terputus: %w", err)
	}
	return Jawaban{}, errors.New("stream agent berakhir tanpa jawaban")
}

// Ringkas meminta agent menggabungkan ingatan lama dengan percakapan terbaru menjadi ingatan baru
func (k *Klien) Ringkas(ctx context.Context, ingatan string, riwayat []Riwayat) (string, error) {
	var hasil hasilRingkas
	err := k.kirimUlang(ctx, "/ringkas", permintaanRingkas{Ingatan: ingatan, Riwayat: riwayat}, &hasil)
	return hasil.Ingatan, err
}

// Embed meminta agent mengubah setiap teks menjadi vektor makna; model yang dipakai ikut dikembalikan
func (k *Klien) Embed(ctx context.Context, jenis string, teks []string) (string, [][]float32, error) {
	var hasil hasilEmbed
	if err := k.kirimUlang(ctx, "/embed", permintaanEmbed{Teks: teks, Jenis: jenis}, &hasil); err != nil {
		return "", nil, err
	}
	if len(hasil.Vektor) != len(teks) {
		return "", nil, fmt.Errorf("agent mengembalikan %d vektor untuk %d teks", len(hasil.Vektor), len(teks))
	}
	return hasil.Model, hasil.Vektor, nil
}

// InfoEmbedding menanyakan apakah embedding aktif di agent dan model mana yang dipakai
func (k *Klien) InfoEmbedding(ctx context.Context) (InfoEmbed, error) {
	var hasil InfoEmbed
	err := k.kirimUlang(ctx, "/embed-info", struct{}{}, &hasil)
	return hasil, err
}

// BacaBerkas meminta agent mengambil teks dari berkas unggahan (PDF, DOCX, atau teks biasa)
func (k *Klien) BacaBerkas(ctx context.Context, nama string, isi []byte) (Berkas, error) {
	var hasil Berkas
	err := k.kirimUlang(ctx, "/baca-berkas", permintaanBerkas{Nama: nama, Isi: base64.StdEncoding.EncodeToString(isi)}, &hasil)
	return hasil, err
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
		return GalatDitolak{Status: resp.StatusCode, Pesan: hasil.Message}
	}
	return json.Unmarshal(hasil.Data, tujuan)
}
