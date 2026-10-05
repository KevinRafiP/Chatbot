package database

import (
	"database/sql"
	"embed"
	"fmt"
	"io/fs"
	"log"
	"path"
	"sort"
)

// Compiler Directive: go:embed
// Embed semua file .sql di folder migrasi

//go:embed migrasi/*.sql
var berkasMigrasi embed.FS

// JalankanMigrasi menjalankan file migrasi yang belum pernah dijalankan, berurutan sesuai nomor
func JalankanMigrasi(db *sql.DB) error {
	_, err := db.Exec(`CREATE TABLE IF NOT EXISTS riwayat_migrasi (
		nama            TEXT PRIMARY KEY,
		dijalankan_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
	)`)
	if err != nil {
		return err
	}

	daftarBerkas, err := fs.Glob(berkasMigrasi, "migrasi/*.sql")
	if err != nil {
		return err
	}
	sort.Strings(daftarBerkas)

	for _, berkas := range daftarBerkas {
		nama := path.Base(berkas)

		var sudahDijalankan bool
		err := db.QueryRow(`SELECT EXISTS(SELECT 1 FROM riwayat_migrasi WHERE nama = $1)`, nama).Scan(&sudahDijalankan)
		if err != nil {
			return err
		}
		if sudahDijalankan {
			continue
		}

		isi, err := berkasMigrasi.ReadFile(berkas)
		if err != nil {
			return err
		}

		tx, err := db.Begin()
		if err != nil {
			return err
		}
		if _, err := tx.Exec(string(isi)); err != nil {
			tx.Rollback()
			return fmt.Errorf("migrasi %s gagal: %w", nama, err)
		}
		if _, err := tx.Exec(`INSERT INTO riwayat_migrasi (nama) VALUES ($1)`, nama); err != nil {
			tx.Rollback()
			return err
		}
		if err := tx.Commit(); err != nil {
			return err
		}
		log.Println("migrasi dijalankan:", nama)
	}
	return nil
}
