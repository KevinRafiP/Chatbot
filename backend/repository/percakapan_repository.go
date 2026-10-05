package repository

import (
	"database/sql"
	"strings"

	"chatbot/backend/model"
)

type PercakapanRepository struct {
	db *sql.DB
}

func BaruPercakapanRepository(db *sql.DB) *PercakapanRepository {
	return &PercakapanRepository{db: db}
}

// Semua mengambil percakapan milik satu pengguna, yang terbaru di atas
func (r *PercakapanRepository) Semua(penggunaID int64) ([]model.Percakapan, error) {
	rows, err := r.db.Query(`SELECT id, judul, diperbarui_pada FROM percakapan
		WHERE pengguna_id = $1 ORDER BY diperbarui_pada DESC`, penggunaID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Percakapan{}
	for rows.Next() {
		var p model.Percakapan
		if err := rows.Scan(&p.ID, &p.Judul, &p.DiperbaruiPada); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// Buat membuat percakapan kosong untuk satu pengguna
func (r *PercakapanRepository) Buat(penggunaID int64) (model.Percakapan, error) {
	var p model.Percakapan
	err := r.db.QueryRow(`INSERT INTO percakapan (pengguna_id) VALUES ($1)
		RETURNING id, judul, diperbarui_pada`, penggunaID).Scan(&p.ID, &p.Judul, &p.DiperbaruiPada)
	return p, err
}

// Milik memeriksa apakah percakapan itu ada dan dimiliki pengguna tersebut
func (r *PercakapanRepository) Milik(id, penggunaID int64) (bool, error) {
	var ada bool
	err := r.db.QueryRow(`SELECT EXISTS(SELECT 1 FROM percakapan WHERE id = $1 AND pengguna_id = $2)`,
		id, penggunaID).Scan(&ada)
	return ada, err
}

// Hapus menghapus percakapan milik pengguna; pesannya ikut terhapus oleh ON DELETE CASCADE
func (r *PercakapanRepository) Hapus(id, penggunaID int64) (bool, error) {
	hasil, err := r.db.Exec(`DELETE FROM percakapan WHERE id = $1 AND pengguna_id = $2`, id, penggunaID)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// UbahJudul mengganti judul percakapan
func (r *PercakapanRepository) UbahJudul(id int64, judul string) error {
	_, err := r.db.Exec(`UPDATE percakapan SET judul = $1 WHERE id = $2`, judul, id)
	return err
}

// DaftarPesan mengambil pesan sebuah percakapan dari yang paling lama; batas 0 berarti semua, selain itu hanya N terakhir
func (r *PercakapanRepository) DaftarPesan(percakapanID int64, batas int) ([]model.Pesan, error) {
	rows, err := r.db.Query(`SELECT id, pengirim, isi, sumber, dibuat_pada FROM (
			SELECT id, pengirim, isi, sumber, dibuat_pada FROM pesan
			WHERE percakapan_id = $1 ORDER BY id DESC LIMIT NULLIF($2, 0)
		) AS terakhir ORDER BY id`, percakapanID, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Pesan{}
	for rows.Next() {
		var p model.Pesan
		var sumber string
		if err := rows.Scan(&p.ID, &p.Pengirim, &p.Isi, &sumber, &p.DibuatPada); err != nil {
			return nil, err
		}
		p.Sumber = pecahSumber(sumber)
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// SimpanPesan menyimpan satu pesan beserta sumbernya dan memperbarui waktu percakapannya
func (r *PercakapanRepository) SimpanPesan(percakapanID int64, pengirim, isi string, sumber []string) (model.Pesan, error) {
	p := model.Pesan{Pengirim: pengirim, Isi: isi, Sumber: pecahSumber(strings.Join(sumber, "\n"))}
	err := r.db.QueryRow(`INSERT INTO pesan (percakapan_id, pengirim, isi, sumber) VALUES ($1, $2, $3, $4)
		RETURNING id, dibuat_pada`, percakapanID, pengirim, isi, strings.Join(p.Sumber, "\n")).Scan(&p.ID, &p.DibuatPada)
	if err != nil {
		return model.Pesan{}, err
	}
	_, err = r.db.Exec(`UPDATE percakapan SET diperbarui_pada = NOW() WHERE id = $1`, percakapanID)
	return p, err
}

// pecahSumber mengubah teks sumber (satu sumber per baris) menjadi daftar
func pecahSumber(teks string) []string {
	daftar := []string{}
	for _, baris := range strings.Split(teks, "\n") {
		if baris = strings.TrimSpace(baris); baris != "" {
			daftar = append(daftar, baris)
		}
	}
	return daftar
}
