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
func (r *AkunRepository) Buat(nama, email, passwordHash, jenis string, terverifikasi bool) (model.Pengguna, error) {
	p := model.Pengguna{Nama: nama, Email: email, Jenis: jenis, Terverifikasi: terverifikasi}
	err := r.db.QueryRow(`INSERT INTO pengguna (nama, email, password_hash, jenis, email_terverifikasi) VALUES ($1, $2, $3, $4, $5)
		RETURNING id`, nama, email, passwordHash, jenis, terverifikasi).Scan(&p.ID)
	return p, err
}

// CariEmail mengambil akun beserta hash password-nya; sql.ErrNoRows bila email belum terdaftar
func (r *AkunRepository) CariEmail(email string) (model.Pengguna, string, error) {
	var p model.Pengguna
	var hash string
	err := r.db.QueryRow(`SELECT id, nama, email, jenis, password_hash, email_terverifikasi FROM pengguna WHERE email = $1`, email).
		Scan(&p.ID, &p.Nama, &p.Email, &p.Jenis, &hash, &p.Terverifikasi)
	return p, hash, err
}

// CariGoogle mengambil akun yang pernah masuk dengan akun Google ini; sql.ErrNoRows bila belum ada
func (r *AkunRepository) CariGoogle(googleID string) (model.Pengguna, error) {
	var p model.Pengguna
	err := r.db.QueryRow(`SELECT id, nama, COALESCE(email, ''), jenis, email_terverifikasi FROM pengguna WHERE google_id = $1`, googleID).
		Scan(&p.ID, &p.Nama, &p.Email, &p.Jenis, &p.Terverifikasi)
	return p, err
}

// SambungGoogle menandai akun milik email itu sebagai akun Google yang sama; emailnya ikut dianggap terverifikasi
func (r *AkunRepository) SambungGoogle(id, googleID string) error {
	// password akun yang emailnya belum terverifikasi dihapus, karena bisa jadi dibuat orang lain memakai email ini
	_, err := r.db.Exec(`UPDATE pengguna SET google_id = $2, email_terverifikasi = TRUE,
		password_hash = CASE WHEN email_terverifikasi THEN password_hash ELSE '' END WHERE id = $1`, id, googleID)
	return err
}

// BuatGoogle membuat akun dari akun Google; password kosong, jadi akun ini hanya bisa masuk lewat Google
// sampai pemiliknya membuat password lewat "Lupa password"
func (r *AkunRepository) BuatGoogle(nama, email, googleID, jenis string) (model.Pengguna, error) {
	p := model.Pengguna{Nama: nama, Email: email, Jenis: jenis, Terverifikasi: true}
	err := r.db.QueryRow(`INSERT INTO pengguna (nama, email, google_id, jenis, email_terverifikasi) VALUES ($1, $2, $3, $4, TRUE)
		RETURNING id`, nama, email, googleID, jenis).Scan(&p.ID)
	return p, err
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
