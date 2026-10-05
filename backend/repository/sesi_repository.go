package repository

import (
	"database/sql"
	"fmt"
	"time"

	"chatbot/backend/model"
)

type SesiRepository struct {
	db *sql.DB
}

func BaruSesiRepository(db *sql.DB) *SesiRepository {
	return &SesiRepository{db: db}
}

// BuatTamu membuat pengguna tamu sekaligus sesi login-nya dalam satu transaksi
func (r *SesiRepository) BuatTamu(tokenHash, perangkat string, kedaluwarsa time.Time) (model.Pengguna, error) {
	tx, err := r.db.Begin()
	if err != nil {
		return model.Pengguna{}, err
	}
	defer tx.Rollback()

	pengguna := model.Pengguna{Jenis: "tamu"}
	err = tx.QueryRow(`INSERT INTO pengguna (nama, jenis) VALUES ('Tamu', 'tamu') RETURNING id`).Scan(&pengguna.ID)
	if err != nil {
		return model.Pengguna{}, err
	}

	pengguna.Nama = fmt.Sprintf("Tamu %d", pengguna.ID)
	if _, err := tx.Exec(`UPDATE pengguna SET nama = $1 WHERE id = $2`, pengguna.Nama, pengguna.ID); err != nil {
		return model.Pengguna{}, err
	}

	_, err = tx.Exec(`INSERT INTO sesi_login (pengguna_id, token_hash, perangkat, kedaluwarsa_pada) VALUES ($1, $2, $3, $4)`,
		pengguna.ID, tokenHash, perangkat, kedaluwarsa)
	if err != nil {
		return model.Pengguna{}, err
	}
	return pengguna, tx.Commit()
}

// CariPengguna mencari pemilik token yang masih berlaku, sekaligus mencatat waktu terakhir dipakai
func (r *SesiRepository) CariPengguna(tokenHash string) (model.Pengguna, error) {
	var pengguna model.Pengguna
	err := r.db.QueryRow(`
		UPDATE sesi_login s SET terakhir_dipakai = NOW()
		FROM pengguna p
		WHERE p.id = s.pengguna_id AND s.token_hash = $1 AND s.kedaluwarsa_pada > NOW()
		RETURNING p.id, p.nama, p.jenis`, tokenHash).Scan(&pengguna.ID, &pengguna.Nama, &pengguna.Jenis)
	return pengguna, err
}

// Hapus menghapus satu sesi login berdasarkan token-nya
func (r *SesiRepository) Hapus(tokenHash string) error {
	_, err := r.db.Exec(`DELETE FROM sesi_login WHERE token_hash = $1`, tokenHash)
	return err
}

// Bersihkan menghapus sesi kedaluwarsa, lalu tamu yang sudah tidak punya sesi (percakapannya ikut terhapus)
func (r *SesiRepository) Bersihkan() (int64, int64, error) {
	hasil, err := r.db.Exec(`DELETE FROM sesi_login WHERE kedaluwarsa_pada <= NOW()`)
	if err != nil {
		return 0, 0, err
	}
	sesi, _ := hasil.RowsAffected()

	hasil, err = r.db.Exec(`DELETE FROM pengguna p WHERE p.jenis = 'tamu'
		AND NOT EXISTS (SELECT 1 FROM sesi_login s WHERE s.pengguna_id = p.id)`)
	if err != nil {
		return sesi, 0, err
	}
	tamu, _ := hasil.RowsAffected()
	return sesi, tamu, nil
}
