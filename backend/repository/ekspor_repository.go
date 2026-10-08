package repository

import (
	"database/sql"
	"strings"
)

type TabelEkspor struct {
	Nama         string
	Kolom        []string
	Urut         string
	UrutCadangan string
}

// DaftarTabelEkspor menentukan tabel dan kolom yang boleh diekspor; token_hash sengaja tidak ikut
var DaftarTabelEkspor = []TabelEkspor{
	{Nama: "pengetahuan", Kolom: []string{"id", "judul", "isi", "kata_kunci", "dibuat_pada"}, Urut: "id"},
	{Nama: "pengguna", Kolom: []string{"id", "nama", "jenis", "dibuat_pada"}, Urut: "dibuat_pada"},
	{Nama: "sesi_login", Kolom: []string{"id", "pengguna_id", "perangkat", "dibuat_pada", "terakhir_dipakai", "kedaluwarsa_pada"}, Urut: "dibuat_pada"},
	{Nama: "percakapan", Kolom: []string{"id", "pengguna_id", "judul", "dibuat_pada", "diperbarui_pada"}, Urut: "dibuat_pada"},
	{Nama: "pesan", Kolom: []string{"id", "percakapan_id", "pengirim", "isi", "sumber", "dibuat_pada"}, Urut: "urutan", UrutCadangan: "id"},
}

type EksporRepository struct {
	db *sql.DB
}

func BaruEksporRepository(db *sql.DB) *EksporRepository {
	return &EksporRepository{db: db}
}

// Baris mengambil semua baris satu tabel sebagai teks, sesuai urutan kolom di TabelEkspor
func (r *EksporRepository) Baris(tabel TabelEkspor) ([][]string, error) {
	kolom := make([]string, len(tabel.Kolom))
	for i, nama := range tabel.Kolom {
		kolom[i] = nama + "::text"
	}
	query := "SELECT " + strings.Join(kolom, ", ") + " FROM " + tabel.Nama + " ORDER BY "

	rows, err := r.db.Query(query + tabel.Urut)
	// Fallback for databases that have not run migration 0005 yet (no urutan column)
	if err != nil && tabel.UrutCadangan != "" {
		rows, err = r.db.Query(query + tabel.UrutCadangan)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	hasil := [][]string{}
	for rows.Next() {
		nilai := make([]sql.NullString, len(tabel.Kolom))
		tujuan := make([]any, len(nilai))
		for i := range nilai {
			tujuan[i] = &nilai[i]
		}
		if err := rows.Scan(tujuan...); err != nil {
			return nil, err
		}

		baris := make([]string, len(nilai))
		for i, n := range nilai {
			baris[i] = n.String
		}
		hasil = append(hasil, baris)
	}
	return hasil, rows.Err()
}
