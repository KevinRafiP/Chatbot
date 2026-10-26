package service

import (
	"context"
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/model"
)

// BatasTeksRiwayatTamu adalah panjang maksimal satu pesan riwayat yang dikirim browser tamu
const BatasTeksRiwayatTamu = 4000

// RiwayatTamu adalah satu pesan lama milik tamu; dikirim browser karena percakapan tamu tidak disimpan di database
type RiwayatTamu struct {
	Peran string `json:"peran"`
	Teks  string `json:"teks"`
}

// JawabTamu menjawab pertanyaan tamu memakai riwayat dari browser-nya, tanpa menyimpan apa pun.
// lampiran juga dikirim browser setiap pesan, karena percakapan tamu tidak disimpan
func (s *ChatbotService) JawabTamu(ctx context.Context, pertanyaan string, riwayat []RiwayatTamu, lampiran *model.Lampiran, kabar agen.Kabar) (HasilChat, error) {
	pertanyaan = strings.TrimSpace(pertanyaan)
	if pertanyaan == "" || len(pertanyaan) > BatasPertanyaan {
		return HasilChat{}, ErrDataTidakValid
	}
	if len(riwayat) > BatasRiwayat {
		riwayat = riwayat[len(riwayat)-BatasRiwayat:]
	}

	bersih := []agen.Riwayat{}
	for _, r := range riwayat {
		if r.Peran != "user" && r.Peran != "asisten" {
			return HasilChat{}, ErrDataTidakValid
		}
		bersih = append(bersih, agen.Riwayat{Peran: r.Peran, Teks: potong(strings.TrimSpace(r.Teks), BatasTeksRiwayatTamu)})
	}
	tambahan := agen.Tambahan{Lampiran: lampiranAgen(bersihkanLampiran(lampiran))}
	return s.Jawab(ctx, pertanyaan, bersih, "", agen.ProfilTamu, tambahan, kabar)
}
