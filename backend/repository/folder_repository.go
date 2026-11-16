package repository

import (
	"database/sql"

	"chatbot/backend/model"
)

type FolderRepository struct {
	db *sql.DB
}

func BaruFolderRepository(db *sql.DB) *FolderRepository {
	return &FolderRepository{db: db}
}

// Semua mengambil folder milik pengguna, urut nama, beserta jumlah percakapan yang belum dihapus
func (r *FolderRepository) Semua(penggunaID string) ([]model.Folder, error) {
	rows, err := r.db.Query(`SELECT f.id, f.nama, COUNT(p.id) FROM folder f
		LEFT JOIN percakapan p ON p.folder_id = f.id AND p.dihapus_pada IS NULL
		WHERE f.pengguna_id = $1 GROUP BY f.id ORDER BY LOWER(f.nama), f.dibuat_pada`, penggunaID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	daftar := []model.Folder{}
	for rows.Next() {
		var f model.Folder
		if err := rows.Scan(&f.ID, &f.Nama, &f.Jumlah); err != nil {
			return nil, err
		}
		daftar = append(daftar, f)
	}
	return daftar, rows.Err()
}

// Jumlah menghitung folder milik pengguna, untuk membatasi banyaknya folder
func (r *FolderRepository) Jumlah(penggunaID string) (int, error) {
	var jumlah int
	err := r.db.QueryRow(`SELECT COUNT(*) FROM folder WHERE pengguna_id = $1`, penggunaID).Scan(&jumlah)
	return jumlah, err
}

// Buat menambah folder kosong
func (r *FolderRepository) Buat(penggunaID, nama string) (model.Folder, error) {
	f := model.Folder{Nama: nama}
	err := r.db.QueryRow(`INSERT INTO folder (pengguna_id, nama) VALUES ($1, $2) RETURNING id`, penggunaID, nama).Scan(&f.ID)
	return f, err
}

// GantiNama mengganti nama folder milik pengguna beserta jumlah percakapannya; sql.ErrNoRows bila folder tidak ada
func (r *FolderRepository) GantiNama(id, penggunaID, nama string) (model.Folder, error) {
	f := model.Folder{ID: id, Nama: nama}
	err := r.db.QueryRow(`UPDATE folder f SET nama = $3 WHERE f.id = $1 AND f.pengguna_id = $2
		RETURNING (SELECT COUNT(*) FROM percakapan p WHERE p.folder_id = f.id AND p.dihapus_pada IS NULL)`,
		id, penggunaID, nama).Scan(&f.Jumlah)
	return f, err
}

// Hapus menghapus folder; percakapan di dalamnya kembali ke daftar biasa (ON DELETE SET NULL)
func (r *FolderRepository) Hapus(id, penggunaID string) (bool, error) {
	return ubahSatu(r.db.Exec(`DELETE FROM folder WHERE id = $1 AND pengguna_id = $2`, id, penggunaID))
}

// Pindahkan memasukkan percakapan ke folder, atau mengeluarkannya bila folderID kosong;
// false bila percakapan atau folder bukan milik pengguna
func (r *FolderRepository) Pindahkan(percakapanID, penggunaID, folderID string) (bool, error) {
	return ubahSatu(r.db.Exec(`UPDATE percakapan SET folder_id = NULLIF($3, '')::uuid
		WHERE id = $1 AND pengguna_id = $2 AND dihapus_pada IS NULL
			AND ($3 = '' OR EXISTS (SELECT 1 FROM folder WHERE id = NULLIF($3, '')::uuid AND pengguna_id = $2))`,
		percakapanID, penggunaID, folderID))
}

// ubahSatu mengubah hasil UPDATE atau DELETE menjadi true bila ada baris yang berubah
func ubahSatu(hasil sql.Result, err error) (bool, error) {
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}
