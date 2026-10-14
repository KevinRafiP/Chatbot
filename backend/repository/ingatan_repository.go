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

// Simpan mengganti ingatan pengguna dengan ringkasan terbaru
func (r *IngatanRepository) Simpan(penggunaID, ingatan string) error {
	_, err := r.db.Exec(`UPDATE pengguna SET ingatan = $2 WHERE id = $1`, penggunaID, ingatan)
	return err
}
