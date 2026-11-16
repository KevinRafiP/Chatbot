package repository

import "database/sql"

type IngatanRepository struct {
	db *sql.DB
}

func BaruIngatanRepository(db *sql.DB) *IngatanRepository {
	return &IngatanRepository{db: db}
}

// Hitung menambah hitungan pertanyaan pengguna, lalu mengembalikan ingatan dan hitungan barunya dalam satu query
func (r *IngatanRepository) Hitung(penggunaID string) (string, int, error) {
	var ingatan string
	var hitung int
	err := r.db.QueryRow(`UPDATE pengguna SET ingatan_hitung = ingatan_hitung + 1
		WHERE id = $1 RETURNING ingatan, ingatan_hitung`, penggunaID).Scan(&ingatan, &hitung)
	return ingatan, hitung, err
}

// Instruksi mengambil instruksi pribadi pengguna; kosong bila belum diisi
func (r *IngatanRepository) Instruksi(penggunaID string) (string, error) {
	var instruksi string
	err := r.db.QueryRow(`SELECT instruksi_pribadi FROM pengguna WHERE id = $1`, penggunaID).Scan(&instruksi)
	return instruksi, err
}

// SimpanInstruksi mengganti instruksi pribadi pengguna
func (r *IngatanRepository) SimpanInstruksi(penggunaID, instruksi string) error {
	_, err := r.db.Exec(`UPDATE pengguna SET instruksi_pribadi = $2 WHERE id = $1`, penggunaID, instruksi)
	return err
}

// Simpan mengganti ingatan pengguna dengan ringkasan terbaru
func (r *IngatanRepository) Simpan(penggunaID, ingatan string) error {
	_, err := r.db.Exec(`UPDATE pengguna SET ingatan = $2 WHERE id = $1`, penggunaID, ingatan)
	return err
}
