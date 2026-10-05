package repository

import (
	"database/sql"

	"chatbot/backend/model"
)

type PengetahuanRepository struct {
	db *sql.DB
}

func BaruPengetahuanRepository(db *sql.DB) *PengetahuanRepository {
	return &PengetahuanRepository{db: db}
}

func (r *PengetahuanRepository) Semua() ([]model.Pengetahuan, error) {
	rows, err := r.db.Query(`SELECT id, judul, isi, kata_kunci, dibuat_pada FROM pengetahuan ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Pengetahuan{}
	for rows.Next() {
		var p model.Pengetahuan
		if err := rows.Scan(&p.ID, &p.Judul, &p.Isi, &p.KataKunci, &p.DibuatPada); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

func (r *PengetahuanRepository) Cari(daftarKata []string, batas int) ([]model.Pengetahuan, error) {
	query := `
		SELECT id, judul, isi, kata_kunci, dibuat_pada
		FROM (
			SELECT *,
				(SELECT COUNT(*) FROM unnest($1::text[]) AS kata
					 WHERE kata = ANY(string_to_array(kata_kunci, ' '))) AS skor
			FROM pengetahuan
		) AS hasil
		WHERE skor > 0
		ORDER BY skor DESC, id
		LIMIT $2`

	rows, err := r.db.Query(query, daftarKata, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Pengetahuan{}
	for rows.Next() {
		var p model.Pengetahuan
		if err := rows.Scan(&p.ID, &p.Judul, &p.Isi, &p.KataKunci, &p.DibuatPada); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// PerbaruiKataKunci mengganti isi kolom kata_kunci pada satu data
func (r *PengetahuanRepository) PerbaruiKataKunci(id int, kataKunci string) error {
	_, err := r.db.Exec(`UPDATE pengetahuan SET kata_kunci = $1 WHERE id = $2`, kataKunci, id)
	return err
}

// Simpan menambah data baru, atau memperbarui data lama jika judulnya sudah ada
func (r *PengetahuanRepository) Simpan(p model.Pengetahuan) (model.Pengetahuan, error) {
	query := `
		INSERT INTO pengetahuan (judul, isi, kata_kunci)
		VALUES ($1, $2, $3)
		ON CONFLICT (judul) DO UPDATE
			SET isi = EXCLUDED.isi, kata_kunci = EXCLUDED.kata_kunci
		RETURNING id, dibuat_pada`

	err := r.db.QueryRow(query, p.Judul, p.Isi, p.KataKunci).Scan(&p.ID, &p.DibuatPada)
	return p, err
}
