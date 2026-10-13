package repository

import (
	"database/sql"

	"chatbot/backend/model"
)

type AkunRepository struct {
	db *sql.DB
}

func BaruAkunRepository(db *sql.DB) *AkunRepository {
	return &AkunRepository{db: db}
}

// Buat menyimpan akun baru; email yang sudah dipakai ditolak oleh UNIQUE di database
func (r *AkunRepository) Buat(nama, email, passwordHash, jenis string) (model.Pengguna, error) {
	p := model.Pengguna{Nama: nama, Email: email, Jenis: jenis}
	err := r.db.QueryRow(`INSERT INTO pengguna (nama, email, password_hash, jenis) VALUES ($1, $2, $3, $4)
		RETURNING id`, nama, email, passwordHash, jenis).Scan(&p.ID)
	return p, err
}

// CariEmail mengambil akun beserta hash password-nya; sql.ErrNoRows bila email belum terdaftar
func (r *AkunRepository) CariEmail(email string) (model.Pengguna, string, error) {
	var p model.Pengguna
	var hash string
	err := r.db.QueryRow(`SELECT id, nama, email, jenis, password_hash FROM pengguna WHERE email = $1`, email).
		Scan(&p.ID, &p.Nama, &p.Email, &p.Jenis, &hash)
	return p, hash, err
}

// UbahJenis mengganti jenis akun berdasarkan email; false bila email belum terdaftar
func (r *AkunRepository) UbahJenis(email, jenis string) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE pengguna SET jenis = $1 WHERE email = $2`, jenis, email)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// PindahkanPercakapan memindahkan percakapan milik tamu ke akun, lalu menghapus tamu itu
func (r *AkunRepository) PindahkanPercakapan(tamuID, akunID string) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`UPDATE percakapan SET pengguna_id = $1 WHERE pengguna_id = $2`, akunID, tamuID); err != nil {
		return err
	}
	if _, err := tx.Exec(`DELETE FROM pengguna WHERE id = $1 AND jenis = 'tamu'`, tamuID); err != nil {
		return err
	}
	return tx.Commit()
}
