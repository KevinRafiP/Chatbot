package database

import (
	"database/sql"
	"embed"
	"fmt"
	"io/fs"
	"path"
	"sort"
	"strings"
)

// Compiler Directive: go:embed
// Embed semua file .sql di folder migrasi

//go:embed migrasi/*.sql
var berkasMigrasi embed.FS

// JalankanMigrasi menjalankan file migrasi yang belum pernah dijalankan, berurutan sesuai nomor;
// hasilnya nama file yang baru dijalankan dan jumlah semua file migrasi
func JalankanMigrasi(db *sql.DB) ([]string, int, error) {
	_, err := db.Exec(`CREATE TABLE IF NOT EXISTS riwayat_migrasi (
		nama            TEXT PRIMARY KEY,
		dijalankan_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	if err != nil {
		return nil, 0, err
	}

	daftarBerkas, err := fs.Glob(berkasMigrasi, "migrasi/*.sql")
	if err != nil {
		return nil, 0, err
	}
	sort.Strings(daftarBerkas)

	var baru []string
	for _, berkas := range daftarBerkas {
		nama := path.Base(berkas)

		var sudahDijalankan bool
		err := db.QueryRow(`SELECT EXISTS(SELECT 1 FROM riwayat_migrasi WHERE nama = $1)`, nama).Scan(&sudahDijalankan)
		if err != nil {
			return nil, 0, err
		}
		if sudahDijalankan {
			continue
		}

		isi, err := berkasMigrasi.ReadFile(berkas)
		if err != nil {
			return nil, 0, err
		}

		tx, err := db.Begin()
		if err != nil {
			return nil, 0, err
		}
		if _, err := tx.Exec(string(isi)); err != nil {
			tx.Rollback()
			return nil, 0, fmt.Errorf("migrasi %s gagal: %w", nama, err)
		}
		if _, err := tx.Exec(`INSERT INTO riwayat_migrasi (nama) VALUES ($1)`, nama); err != nil {
			tx.Rollback()
			return nil, 0, err
		}
		if err := tx.Commit(); err != nil {
			return nil, 0, err
		}
		baru = append(baru, nama)
	}
	return baru, len(daftarBerkas), nil
}

// KeteranganMigrasi meringkas hasil JalankanMigrasi untuk tabel saat menyala
func KeteranganMigrasi(baru []string, jumlah int) string {
	if len(baru) == 0 {
		return fmt.Sprintf("%d berkas, semua sudah dijalankan", jumlah)
	}
	return fmt.Sprintf("%d berkas, baru dijalankan: %s", jumlah, strings.Join(baru, ", "))
}
