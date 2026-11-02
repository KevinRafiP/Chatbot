package repository

import (
	"database/sql"
	"strings"
	"time"

	"chatbot/backend/model"
)

type KinerjaRepository struct {
	db *sql.DB
}

func BaruKinerjaRepository(db *sql.DB) *KinerjaRepository {
	return &KinerjaRepository{db: db}
}

// Simpan menambah satu catatan kinerja
func (r *KinerjaRepository) Simpan(k model.Kinerja) error {
	_, err := r.db.Exec(`INSERT INTO kinerja_jawaban (profil, berhasil, galat, lama_ms, token_masuk, token_keluar, panggilan_llm, alat, panjang_jawaban)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
		k.Profil, k.Berhasil, k.Galat, k.LamaMs, k.TokenMasuk, k.TokenKeluar, k.PanggilanLLM, strings.Join(k.Alat, ","), k.PanjangJawaban)
	return err
}

// HapusSebelum menghapus catatan yang lebih lama dari batas waktu
func (r *KinerjaRepository) HapusSebelum(batas time.Time) (int64, error) {
	hasil, err := r.db.Exec(`DELETE FROM kinerja_jawaban WHERE dibuat_pada < $1`, batas)
	if err != nil {
		return 0, err
	}
	return hasil.RowsAffected()
}

// Laporan merangkum catatan sejak hari terakhir: total, per profil, alat terbanyak, dan beberapa catatan terbaru
func (r *KinerjaRepository) Laporan(hari, batasAlat, batasTerbaru int) (model.LaporanKinerja, error) {
	laporan := model.LaporanKinerja{Hari: hari, PerProfil: []model.StatistikKinerja{}, Alat: []model.PemakaianAlat{}, Terbaru: []model.Kinerja{}}
	sejak := time.Now().AddDate(0, 0, -hari)

	// ROLLUP menambah baris total per jenis (GROUPING = 1) di samping baris per profil; total "jawaban" tidak ikut
	// menghitung peringkasan percakapan ('ringkasan' sama dengan service.ProfilRingkasan) yang berjalan di latar belakang
	rows, err := r.db.Query(`SELECT GROUPING(profil), jenis, COALESCE(profil, ''), COUNT(*), COUNT(*) FILTER (WHERE NOT berhasil),
			COALESCE(AVG(lama_ms), 0)::BIGINT,
			COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY lama_ms), 0)::BIGINT,
			COALESCE(AVG(token_masuk + token_keluar) FILTER (WHERE berhasil), 0)::BIGINT,
			COALESCE(SUM(token_masuk), 0), COALESCE(SUM(token_keluar), 0)
		FROM (SELECT *, CASE WHEN profil = 'ringkasan' THEN 'ringkasan' ELSE 'jawaban' END AS jenis
			FROM kinerja_jawaban WHERE dibuat_pada >= $1) AS k
		GROUP BY jenis, ROLLUP(profil) ORDER BY COUNT(*) DESC`, sejak)
	if err != nil {
		return laporan, err
	}
	defer rows.Close()
	for rows.Next() {
		var total int
		var jenis string
		var s model.StatistikKinerja
		if err := rows.Scan(&total, &jenis, &s.Profil, &s.Jumlah, &s.Gagal, &s.RataLamaMs, &s.P90LamaMs, &s.RataToken, &s.TokenMasuk, &s.TokenKeluar); err != nil {
			return laporan, err
		}
		switch {
		case total == 0:
			laporan.PerProfil = append(laporan.PerProfil, s)
		case jenis == "jawaban":
			laporan.Semua = s
		}
	}
	if err := rows.Err(); err != nil {
		return laporan, err
	}

	rows, err = r.db.Query(`SELECT nama, COUNT(*) FROM kinerja_jawaban, unnest(string_to_array(NULLIF(alat, ''), ',')) AS nama
		WHERE dibuat_pada >= $1 GROUP BY nama ORDER BY COUNT(*) DESC, nama LIMIT $2`, sejak, batasAlat)
	if err != nil {
		return laporan, err
	}
	defer rows.Close()
	for rows.Next() {
		var a model.PemakaianAlat
		if err := rows.Scan(&a.Nama, &a.Jumlah); err != nil {
			return laporan, err
		}
		laporan.Alat = append(laporan.Alat, a)
	}
	if err := rows.Err(); err != nil {
		return laporan, err
	}

	rows, err = r.db.Query(`SELECT profil, berhasil, galat, lama_ms, token_masuk, token_keluar, panggilan_llm, alat, panjang_jawaban, dibuat_pada
		FROM kinerja_jawaban WHERE dibuat_pada >= $1 ORDER BY dibuat_pada DESC LIMIT $2`, sejak, batasTerbaru)
	if err != nil {
		return laporan, err
	}
	defer rows.Close()
	for rows.Next() {
		var k model.Kinerja
		var alat string
		if err := rows.Scan(&k.Profil, &k.Berhasil, &k.Galat, &k.LamaMs, &k.TokenMasuk, &k.TokenKeluar, &k.PanggilanLLM, &alat, &k.PanjangJawaban, &k.DibuatPada); err != nil {
			return laporan, err
		}
		k.Alat = []string{}
		if alat != "" {
			k.Alat = strings.Split(alat, ",")
		}
		laporan.Terbaru = append(laporan.Terbaru, k)
	}
	return laporan, rows.Err()
}
