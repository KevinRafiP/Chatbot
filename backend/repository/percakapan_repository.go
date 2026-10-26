package repository

import (
	"database/sql"
	"encoding/json"
	"errors"
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
func (r *PercakapanRepository) Semua(penggunaID string) ([]model.Percakapan, error) {
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
func (r *PercakapanRepository) Buat(penggunaID string) (model.Percakapan, error) {
	var p model.Percakapan
	err := r.db.QueryRow(`INSERT INTO percakapan (pengguna_id) VALUES ($1)
		RETURNING id, judul, diperbarui_pada`, penggunaID).Scan(&p.ID, &p.Judul, &p.DiperbaruiPada)
	return p, err
}

// Milik memeriksa apakah percakapan itu ada dan dimiliki pengguna tersebut
func (r *PercakapanRepository) Milik(id, penggunaID string) (bool, error) {
	var ada bool
	err := r.db.QueryRow(`SELECT EXISTS(SELECT 1 FROM percakapan WHERE id = $1 AND pengguna_id = $2)`,
		id, penggunaID).Scan(&ada)
	return ada, err
}

// Hapus menghapus percakapan milik pengguna; pesannya ikut terhapus oleh ON DELETE CASCADE
func (r *PercakapanRepository) Hapus(id, penggunaID string) (bool, error) {
	hasil, err := r.db.Exec(`DELETE FROM percakapan WHERE id = $1 AND pengguna_id = $2`, id, penggunaID)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// UbahJudul mengganti judul percakapan
func (r *PercakapanRepository) UbahJudul(id string, judul string) error {
	_, err := r.db.Exec(`UPDATE percakapan SET judul = $1 WHERE id = $2`, judul, id)
	return err
}

// GantiJudul mengganti judul percakapan milik pengguna; sql.ErrNoRows bila percakapan tidak ada
func (r *PercakapanRepository) GantiJudul(id, penggunaID, judul string) (model.Percakapan, error) {
	var p model.Percakapan
	err := r.db.QueryRow(`UPDATE percakapan SET judul = $1 WHERE id = $2 AND pengguna_id = $3
		RETURNING id, judul, diperbarui_pada`, judul, id, penggunaID).Scan(&p.ID, &p.Judul, &p.DiperbaruiPada)
	return p, err
}

// DaftarPesan mengambil pesan sebuah percakapan dari yang paling lama; batas 0 berarti semua, selain itu hanya N terakhir
func (r *PercakapanRepository) DaftarPesan(percakapanID string, batas int) ([]model.Pesan, error) {
	rows, err := r.db.Query(`SELECT id, pengirim, isi, sumber, favorit, lampiran_nama, dibuat_pada FROM (
		SELECT id, urutan, pengirim, isi, sumber, favorit, lampiran_nama, dibuat_pada FROM pesan
			WHERE percakapan_id = $1 ORDER BY urutan DESC LIMIT NULLIF($2, 0)
		) AS terakhir ORDER BY urutan`, percakapanID, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Pesan{}
	for rows.Next() {
		var p model.Pesan
		var sumber string
		if err := rows.Scan(&p.ID, &p.Pengirim, &p.Isi, &sumber, &p.Favorit, &p.Lampiran, &p.DibuatPada); err != nil {
			return nil, err
		}
		p.Sumber = pecahSumber(sumber)
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// SimpanPesan menyimpan satu pesan beserta sumbernya dan memperbarui waktu percakapannya
func (r *PercakapanRepository) SimpanPesan(percakapanID string, pengirim, isi string, sumber []model.Sumber) (model.Pesan, error) {
	return r.SimpanPesanLampiran(percakapanID, pengirim, isi, sumber, model.Lampiran{})
}

// SimpanPesanLampiran sama seperti SimpanPesan, ditambah berkas yang diunggah bersama pesan itu
func (r *PercakapanRepository) SimpanPesanLampiran(percakapanID string, pengirim, isi string, sumber []model.Sumber, lampiran model.Lampiran) (model.Pesan, error) {
	if sumber == nil {
		sumber = []model.Sumber{}
	}
	teksSumber, err := json.Marshal(sumber)
	if err != nil {
		return model.Pesan{}, err
	}

	p := model.Pesan{Pengirim: pengirim, Isi: isi, Sumber: sumber, Lampiran: lampiran.Nama}
	err = r.db.QueryRow(`INSERT INTO pesan (percakapan_id, pengirim, isi, sumber, lampiran_nama, lampiran_teks) VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, dibuat_pada`, percakapanID, pengirim, isi, string(teksSumber), lampiran.Nama, lampiran.Teks).Scan(&p.ID, &p.DibuatPada)
	if err != nil {
		return model.Pesan{}, err
	}
	_, err = r.db.Exec(`UPDATE percakapan SET diperbarui_pada = NOW() WHERE id = $1`, percakapanID)
	return p, err
}

// LampiranTerakhir mengambil berkas terbaru di antara batas pesan terakhir sebuah percakapan;
// kosong bila tidak ada, agar berkas lama tidak terus ikut ke pertanyaan yang sudah jauh
func (r *PercakapanRepository) LampiranTerakhir(percakapanID string, batas int) (model.Lampiran, error) {
	var l model.Lampiran
	err := r.db.QueryRow(`SELECT lampiran_nama, lampiran_teks FROM (
			SELECT lampiran_nama, lampiran_teks, urutan FROM pesan WHERE percakapan_id = $1 ORDER BY urutan DESC LIMIT $2
		) AS terakhir WHERE lampiran_nama <> '' ORDER BY urutan DESC LIMIT 1`, percakapanID, batas).Scan(&l.Nama, &l.Teks)
	if errors.Is(err, sql.ErrNoRows) {
		return model.Lampiran{}, nil
	}
	return l, err
}

// UbahFavorit menandai atau melepas bintang sebuah pesan, hanya bila percakapannya milik pengguna itu
func (r *PercakapanRepository) UbahFavorit(pesanID, penggunaID string, favorit bool) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE pesan p SET favorit = $3 FROM percakapan c
		WHERE p.id = $1 AND p.percakapan_id = c.id AND c.pengguna_id = $2`, pesanID, penggunaID, favorit)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// DaftarFavorit mengambil pesan berbintang dari semua percakapan milik pengguna, yang terbaru di atas
func (r *PercakapanRepository) DaftarFavorit(penggunaID string, batas int) ([]model.PesanFavorit, error) {
	rows, err := r.db.Query(`SELECT p.id, p.pengirim, p.isi, p.sumber, p.dibuat_pada, c.id, c.judul
		FROM pesan p JOIN percakapan c ON c.id = p.percakapan_id
		WHERE c.pengguna_id = $1 AND p.favorit ORDER BY p.dibuat_pada DESC LIMIT $2`, penggunaID, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.PesanFavorit{}
	for rows.Next() {
		var p model.PesanFavorit
		var sumber string
		if err := rows.Scan(&p.ID, &p.Pengirim, &p.Isi, &sumber, &p.DibuatPada, &p.PercakapanID, &p.JudulPercakapan); err != nil {
			return nil, err
		}
		p.Sumber = pecahSumber(sumber)
		p.Favorit = true
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// pecahSumber membaca kolom sumber: bentuk baru berupa JSON, bentuk lama satu sumber per baris
func pecahSumber(teks string) []model.Sumber {
	daftar := []model.Sumber{}
	if strings.HasPrefix(teks, "[") && json.Unmarshal([]byte(teks), &daftar) == nil {
		return daftar
	}

	daftar = []model.Sumber{}
	for _, baris := range strings.Split(teks, "\n") {
		baris = strings.TrimSpace(baris)
		if baris == "" {
			continue
		}
		if strings.HasPrefix(baris, "http://") || strings.HasPrefix(baris, "https://") {
			daftar = append(daftar, model.Sumber{Judul: baris, URL: baris})
		} else {
			daftar = append(daftar, model.Sumber{Judul: baris})
		}
	}
	return daftar
}
