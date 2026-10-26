package service

import (
	"strings"

	"chatbot/backend/agen"
	"chatbot/backend/model"
)

const (
	// BatasTeksLampiran adalah panjang maksimal teks berkas yang disimpan dan dikirim ke agent
	BatasTeksLampiran = 30000
	batasNamaLampiran = 200
)

// bersihkanLampiran merapikan nama dan teks berkas dari browser; nil bila teksnya kosong.
// Huruf NUL dan UTF-8 rusak dibuang karena ditolak kolom TEXT Postgres
func bersihkanLampiran(l *model.Lampiran) *model.Lampiran {
	if l == nil {
		return nil
	}
	teks := strings.TrimSpace(strings.ToValidUTF8(strings.ReplaceAll(l.Teks, "\x00", ""), ""))
	if teks == "" {
		return nil
	}
	if huruf := []rune(teks); len(huruf) > BatasTeksLampiran {
		teks = string(huruf[:BatasTeksLampiran])
	}
	nama := potong(strings.TrimSpace(strings.ToValidUTF8(strings.ReplaceAll(l.Nama, "\x00", ""), "")), batasNamaLampiran)
	if nama == "" {
		nama = "berkas"
	}
	return &model.Lampiran{Nama: nama, Teks: teks}
}

func lampiranAgen(l *model.Lampiran) *agen.Lampiran {
	if l == nil || l.Teks == "" {
		return nil
	}
	return &agen.Lampiran{Nama: l.Nama, Teks: l.Teks}
}
