package repository

import (
	"time"

	"chatbot/backend/model"
)

// SimpanVerifikasi menyimpan token verifikasi baru; token lama milik pengguna itu dihapus dulu
func (r *AkunRepository) SimpanVerifikasi(penggunaID, tokenHash string, ingat bool, kedaluwarsa time.Time) error {
	tx, err := r.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	if _, err := tx.Exec(`DELETE FROM verifikasi_email WHERE pengguna_id = $1`, penggunaID); err != nil {
		return err
	}
	_, err = tx.Exec(`INSERT INTO verifikasi_email (token_hash, pengguna_id, ingat, kedaluwarsa_pada) VALUES ($1, $2, $3, $4)`,
		tokenHash, penggunaID, ingat, kedaluwarsa)
	if err != nil {
		return err
	}
	return tx.Commit()
}

// TerakhirDikirim mengembalikan waktu token verifikasi terakhir dibuat; sql.ErrNoRows bila belum ada
func (r *AkunRepository) TerakhirDikirim(penggunaID string) (time.Time, error) {
	var waktu time.Time
	err := r.db.QueryRow(`SELECT dibuat_pada FROM verifikasi_email WHERE pengguna_id = $1`, penggunaID).Scan(&waktu)
	return waktu, err
}

// PakaiVerifikasi menghapus token yang masih berlaku, menandai email-nya terverifikasi, lalu mengembalikan akunnya;
// sql.ErrNoRows bila token salah atau kedaluwarsa
func (r *AkunRepository) PakaiVerifikasi(tokenHash string) (model.Pengguna, bool, error) {
	tx, err := r.db.Begin()
	if err != nil {
		return model.Pengguna{}, false, err
	}
	defer tx.Rollback()

	var penggunaID string
	var ingat bool
	err = tx.QueryRow(`DELETE FROM verifikasi_email WHERE token_hash = $1 AND kedaluwarsa_pada > NOW()
		RETURNING pengguna_id, ingat`, tokenHash).Scan(&penggunaID, &ingat)
	if err != nil {
		return model.Pengguna{}, false, err
	}

	p := model.Pengguna{Terverifikasi: true}
	err = tx.QueryRow(`UPDATE pengguna SET email_terverifikasi = TRUE WHERE id = $1
		RETURNING id, nama, jenis, email`, penggunaID).Scan(&p.ID, &p.Nama, &p.Jenis, &p.Email)
	if err != nil {
		return model.Pengguna{}, false, err
	}
	return p, ingat, tx.Commit()
}
