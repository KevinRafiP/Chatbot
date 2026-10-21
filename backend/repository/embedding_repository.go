package repository

import (
	"database/sql"
	"fmt"
	"strconv"
	"strings"

	"chatbot/backend/model"
)

type EmbeddingRepository struct {
	db *sql.DB
}

func BaruEmbeddingRepository(db *sql.DB) *EmbeddingRepository {
	return &EmbeddingRepository{db: db}
}

// HasilMirip adalah satu potongan hasil pencarian makna beserta kemiripannya (1 = sama persis)
type HasilMirip struct {
	model.Pengetahuan
	Skor float64
}

// Tersedia memeriksa apakah tabel embedding sudah dibuat migrasi (butuh ekstensi pgvector)
func (r *EmbeddingRepository) Tersedia() (bool, error) {
	var ada bool
	err := r.db.QueryRow(`SELECT to_regclass('embedding_potongan') IS NOT NULL`).Scan(&ada)
	return ada, err
}

// PengetahuanBerubah mengambil data yang belum dipotong atau isinya berubah sejak terakhir dipotong
func (r *EmbeddingRepository) PengetahuanBerubah(batas int) ([]model.Pengetahuan, error) {
	rows, err := r.db.Query(`
		SELECT p.id, p.judul, p.isi, p.kata_kunci, p.dibuat_pada
		FROM pengetahuan p
		WHERE NOT EXISTS (
			SELECT 1 FROM potongan_pengetahuan k
			WHERE k.pengetahuan_id = p.id AND k.sidik = md5(p.judul || E'\n' || p.isi))
		ORDER BY p.id
		LIMIT $1`, batas)
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

// GantiPotongan mengganti semua potongan satu data; embedding potongan lama ikut terhapus
func (r *EmbeddingRepository) GantiPotongan(pengetahuanID int, sidik string, daftarIsi []string) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM potongan_pengetahuan WHERE pengetahuan_id = $1`, pengetahuanID); err != nil {
		return err
	}
	for urutan, isi := range daftarIsi {
		_, err := tx.Exec(`INSERT INTO potongan_pengetahuan (pengetahuan_id, urutan, isi, sidik) VALUES ($1, $2, $3, $4)`,
			pengetahuanID, urutan, isi, sidik)
		if err != nil {
			return err
		}
	}
	return tx.Commit()
}

// PotonganTanpaEmbedding mengambil potongan yang belum punya vektor dari model ini
func (r *EmbeddingRepository) PotonganTanpaEmbedding(namaModel string, batas int) ([]model.Potongan, error) {
	rows, err := r.db.Query(`
		SELECT k.id, p.judul, k.isi
		FROM potongan_pengetahuan k
		JOIN pengetahuan p ON p.id = k.pengetahuan_id
		WHERE NOT EXISTS (SELECT 1 FROM embedding_potongan e WHERE e.potongan_id = k.id AND e.model = $1)
		ORDER BY k.id
		LIMIT $2`, namaModel, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Potongan{}
	for rows.Next() {
		var p model.Potongan
		if err := rows.Scan(&p.ID, &p.Judul, &p.Isi); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// SimpanEmbedding menyimpan vektor satu potongan, atau menggantinya jika model ini sudah pernah menyimpan
func (r *EmbeddingRepository) SimpanEmbedding(namaModel string, potonganID int64, vektor []float32) error {
	_, err := r.db.Exec(`
		INSERT INTO embedding_potongan (potongan_id, model, dimensi, vektor)
		VALUES ($1, $2, $3, $4::vector)
		ON CONFLICT (potongan_id, model) DO UPDATE
			SET dimensi = EXCLUDED.dimensi, vektor = EXCLUDED.vektor, dibuat_pada = NOW()`,
		potonganID, namaModel, len(vektor), teksVektor(vektor))
	return err
}

// CariMirip mengambil potongan yang maknanya paling dekat dengan vektor pertanyaan, dari model yang sama.
// Nama model dan dimensi ditulis langsung di query (bukan parameter) agar Postgres bisa memakai
// indeks HNSW per model; nama model sudah diperiksa polanya di EmbeddingService
func (r *EmbeddingRepository) CariMirip(namaModel string, vektor []float32, batas int) ([]HasilMirip, error) {
	jarak := fmt.Sprintf("e.vektor::vector(%[1]d) <=> $1::vector(%[1]d)", len(vektor))
	query := fmt.Sprintf(`
		SELECT p.id, p.judul, k.isi, p.kata_kunci, p.dibuat_pada, 1 - (%[1]s) AS skor
		FROM embedding_potongan e
		JOIN potongan_pengetahuan k ON k.id = e.potongan_id
		JOIN pengetahuan p ON p.id = k.pengetahuan_id
		WHERE e.model = '%[2]s'
		ORDER BY %[1]s
		LIMIT $2`, jarak, strings.ReplaceAll(namaModel, "'", "''"))

	rows, err := r.db.Query(query, teksVektor(vektor), batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []HasilMirip{}
	for rows.Next() {
		var h HasilMirip
		if err := rows.Scan(&h.ID, &h.Judul, &h.Isi, &h.KataKunci, &h.DibuatPada, &h.Skor); err != nil {
			return nil, err
		}
		daftar = append(daftar, h)
	}
	return daftar, rows.Err()
}

// teksVektor menulis vektor dalam format pgvector, contoh [0.1,-0.2,0.3]
func teksVektor(vektor []float32) string {
	bagian := make([]string, len(vektor))
	for i, nilai := range vektor {
		bagian[i] = strconv.FormatFloat(float64(nilai), 'g', -1, 32)
	}
	return "[" + strings.Join(bagian, ",") + "]"
}
