package service

import (
	"sort"
	"strings"
)

var kataAbaikan = map[string]bool{
	"apa": true, "apakah": true, "yang": true, "di": true, "ke": true, "dari": true,
	"dan": true, "atau": true, "itu": true, "ini": true, "saya": true, "aku": true,
	"bagaimana": true, "berapa": true, "kapan": true, "cara": true, "untuk": true,
	"dengan": true, "ada": true, "bisa": true, "mau": true, "tolong": true,
	"siapa": true, "mana": true, "dimana": true, "kenapa": true, "mengapa": true,
	"adalah": true, "tahun": true, "kalau": true, "jika": true, "tentang": true,
}

// PecahKata mengubah kalimat menjadi daftar kata penting
func PecahKata(kalimat string) []string {
	kalimat = strings.ToLower(kalimat)
	potongan := strings.FieldsFunc(kalimat, func(h rune) bool {
		return !(h >= 'a' && h <= 'z') && !(h >= '0' && h <= '9')
	})

	hasil := []string{}
	for _, kata := range potongan {
		if len(kata) < 3 || kataAbaikan[kata] {
			continue
		}
		hasil = append(hasil, kata)
	}
	return hasil
}

// SusunKataKunci menggabungkan kata penting dari judul, isi, dan kata kunci lama tanpa duplikat
func SusunKataKunci(judul, isi, kataKunciLama string) string {
	semuaKata := PecahKata(judul + " " + isi + " " + kataKunciLama)

	sudahAda := map[string]bool{}
	hasil := []string{}
	for _, kata := range semuaKata {
		if sudahAda[kata] {
			continue
		}
		sudahAda[kata] = true
		hasil = append(hasil, kata)
	}

	sort.Strings(hasil)
	return strings.Join(hasil, " ")
}
