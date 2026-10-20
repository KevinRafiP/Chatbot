package repository

import (
	"time"

	"chatbot/backend/model"
)

// SimpanAturUlang menyimpan token atur ulang password baru; token lama milik pengguna itu
// dan semua token yang sudah kedaluwarsa dihapus dulu
func (r *AkunRepository) SimpanAturUlang(penggunaID, tokenHash string, kedaluwarsa time.Time) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM atur_ulang_password WHERE pengguna_id = $1 OR kedaluwarsa_pada <= NOW()`, penggunaID); err != nil {
		return err
	}
	_, err = tx.Exec(`INSERT INTO atur_ulang_password (token_hash, pengguna_id, kedaluwarsa_pada) VALUES ($1, $2, $3)`,
		tokenHash, penggunaID, kedaluwarsa)
	if err != nil {
		return err
	}
	return tx.Commit()
}

// TerakhirAturUlang mengembalikan waktu token atur ulang terakhir dibuat; sql.ErrNoRows bila belum ada
func (r *AkunRepository) TerakhirAturUlang(penggunaID string) (time.Time, error) {
	var waktu time.Time
	err := r.db.QueryRow(`SELECT dibuat_pada FROM atur_ulang_password WHERE pengguna_id = $1`, penggunaID).Scan(&waktu)
	return waktu, err
}

// PakaiAturUlang menghapus token yang masih berlaku, mengganti password, lalu mengeluarkan akun dari semua perangkat.
// Email ikut dianggap terverifikasi karena link-nya dibuka dari kotak masuk; sql.ErrNoRows bila token salah atau kedaluwarsa
func (r *AkunRepository) PakaiAturUlang(tokenHash, passwordHash string) (model.Pengguna, error) {
	tx, err := r.db.Begin()
	if err != nil {
		return model.Pengguna{}, err
	}
	defer tx.Rollback()

	var penggunaID string
	err = tx.QueryRow(`DELETE FROM atur_ulang_password WHERE token_hash = $1 AND kedaluwarsa_pada > NOW()
		RETURNING pengguna_id`, tokenHash).Scan(&penggunaID)
	if err != nil {
		return model.Pengguna{}, err
	}

	p := model.Pengguna{Terverifikasi: true}
	err = tx.QueryRow(`UPDATE pengguna SET password_hash = $1, email_terverifikasi = TRUE WHERE id = $2
		RETURNING id, nama, jenis, email`, passwordHash, penggunaID).Scan(&p.ID, &p.Nama, &p.Jenis, &p.Email)
	if err != nil {
		return model.Pengguna{}, err
	}
	if _, err := tx.Exec(`DELETE FROM sesi_login WHERE pengguna_id = $1`, penggunaID); err != nil {
		return model.Pengguna{}, err
	}
	if _, err := tx.Exec(`DELETE FROM verifikasi_email WHERE pengguna_id = $1`, penggunaID); err != nil {
		return model.Pengguna{}, err
	}
	return p, tx.Commit()
}
