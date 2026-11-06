package repository

import (
	"database/sql"
	"fmt"
	"strings"
	"time"

	"chatbot/backend/model"
)

// AkunTamu dan AkunLain adalah kunci akun untuk semua tamu dan untuk catatan tanpa akun (sebelum fitur per akun
// atau akunnya sudah dihapus); akun terdaftar memakai id-nya
const (
	AkunTamu = "tamu"
	AkunLain = "lain"
)

// kunciAkun mengelompokkan catatan kinerja_jawaban (alias k) per akun
const kunciAkun = `CASE WHEN k.jenis_akun = 'tamu' THEN 'tamu' WHEN k.pengguna_id IS NULL THEN 'lain' ELSE k.pengguna_id::text END`

// saringAkun menambah syarat akun pada query kinerja_jawaban (alias k); akun kosong berarti semua akun
func saringAkun(akun string, args []any) (string, []any) {
	if akun == "" {
		return "", args
	}
	args = append(args, akun)
	return fmt.Sprintf(" AND %s = $%d", kunciAkun, len(args)), args
}

// saringPesan menambah syarat akun pada query pesan (alias p): hanya percakapan milik akun itu.
// Percakapan tamu tidak disimpan, jadi tamu dan catatan tanpa akun tidak punya penilaian
func saringPesan(akun string, args []any) (string, []any) {
	switch akun {
	case "":
		return "", args
	case AkunTamu, AkunLain:
		return " AND FALSE", args
	}
	args = append(args, akun)
	return fmt.Sprintf(" AND p.percakapan_id IN (SELECT id FROM percakapan WHERE pengguna_id = $%d)", len(args)), args
}

type KinerjaRepository struct {
	db *sql.DB
}

func BaruKinerjaRepository(db *sql.DB) *KinerjaRepository {
	return &KinerjaRepository{db: db}
}

// Simpan menambah satu catatan kinerja; PenggunaID kosong berarti tanpa akun (misalnya tamu yang sudah dihapus)
func (r *KinerjaRepository) Simpan(k model.Kinerja) error {
	_, err := r.db.Exec(`INSERT INTO kinerja_jawaban (profil, berhasil, galat, lama_ms, token_masuk, token_keluar, panggilan_llm, alat, panjang_jawaban, pengguna_id, jenis_akun)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULLIF($10, '')::uuid, $11)`,
		k.Profil, k.Berhasil, k.Galat, k.LamaMs, k.TokenMasuk, k.TokenKeluar, k.PanggilanLLM, strings.Join(k.Alat, ","), k.PanjangJawaban,
		k.PenggunaID, k.JenisAkun)
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

// Laporan merangkum catatan dari sejak sampai sebelum sampai: total, per profil, dan alat terbanyak; akun kosong = semua akun
func (r *KinerjaRepository) Laporan(sejak, sampai time.Time, akun string, batasAlat int) (model.LaporanKinerja, error) {
	laporan := model.LaporanKinerja{PerProfil: []model.StatistikKinerja{}, Alat: []model.PemakaianAlat{}, PerAkun: []model.KinerjaAkun{},
		Penilaian: []model.PenilaianJawaban{}, TidakDisukai: []model.JawabanDinilai{}}

	// ROLLUP menambah baris total per jenis (GROUPING = 1) di samping baris per profil; total "jawaban" tidak ikut
	// menghitung peringkasan percakapan ('ringkasan' sama dengan service.ProfilRingkasan) yang berjalan di latar belakang
	syarat, args := saringAkun(akun, []any{sejak, sampai})
	rows, err := r.db.Query(`SELECT GROUPING(profil), jenis, COALESCE(profil, ''), COUNT(*), COUNT(*) FILTER (WHERE NOT berhasil),
			COALESCE(AVG(lama_ms), 0)::BIGINT,
			COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY lama_ms), 0)::BIGINT,
			COALESCE(AVG(token_masuk + token_keluar) FILTER (WHERE berhasil), 0)::BIGINT,
			COALESCE(SUM(token_masuk), 0), COALESCE(SUM(token_keluar), 0)
		FROM (SELECT k.*, CASE WHEN k.profil = 'ringkasan' THEN 'ringkasan' ELSE 'jawaban' END AS jenis
			FROM kinerja_jawaban k WHERE k.dibuat_pada >= $1 AND k.dibuat_pada < $2`+syarat+`) AS k
		GROUP BY jenis, ROLLUP(profil) ORDER BY COUNT(*) DESC`, args...)
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

	syarat, args = saringAkun(akun, []any{sejak, sampai, batasAlat})
	rows, err = r.db.Query(`SELECT nama, COUNT(*) FROM kinerja_jawaban k, unnest(string_to_array(NULLIF(k.alat, ''), ',')) AS nama
		WHERE k.dibuat_pada >= $1 AND k.dibuat_pada < $2`+syarat+` GROUP BY nama ORDER BY COUNT(*) DESC, nama LIMIT $3`, args...)
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
	return laporan, rows.Err()
}

// PerAkun merangkum jawaban setiap akun (tanpa peringkasan percakapan), yang paling banyak bertanya lebih dulu
func (r *KinerjaRepository) PerAkun(sejak, sampai time.Time, batas int) ([]model.KinerjaAkun, error) {
	rows, err := r.db.Query(`SELECT `+kunciAkun+` AS kunci, COALESCE(MAX(p.nama), ''), COALESCE(MAX(p.email), ''),
			COALESCE(MAX(p.jenis), MAX(k.jenis_akun)), COUNT(*), COUNT(*) FILTER (WHERE NOT k.berhasil),
			COALESCE(AVG(k.lama_ms), 0)::BIGINT, COALESCE(SUM(k.token_masuk), 0), COALESCE(SUM(k.token_keluar), 0), MAX(k.dibuat_pada)
		FROM kinerja_jawaban k LEFT JOIN pengguna p ON p.id = k.pengguna_id
		WHERE k.dibuat_pada >= $1 AND k.dibuat_pada < $2 AND k.profil <> 'ringkasan'
		GROUP BY kunci ORDER BY COUNT(*) DESC, MAX(k.dibuat_pada) DESC LIMIT $3`, sejak, sampai, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	daftar := []model.KinerjaAkun{}
	for rows.Next() {
		var a model.KinerjaAkun
		if err := rows.Scan(&a.Akun, &a.Nama, &a.Email, &a.Jenis, &a.Jumlah, &a.Gagal, &a.RataLamaMs, &a.TokenMasuk, &a.TokenKeluar, &a.Terakhir); err != nil {
			return nil, err
		}
		// nama tamu dan catatan tanpa akun tidak berarti; label ditentukan di halaman admin
		if a.Akun == AkunTamu || a.Akun == AkunLain {
			a.Nama, a.Email = "", ""
		}
		daftar = append(daftar, a)
	}
	return daftar, rows.Err()
}

// Jumlah menghitung semua catatan dari sejak sampai sebelum sampai; akun kosong = semua akun
func (r *KinerjaRepository) Jumlah(sejak, sampai time.Time, akun string) (int, error) {
	syarat, args := saringAkun(akun, []any{sejak, sampai})
	var jumlah int
	err := r.db.QueryRow(`SELECT COUNT(*) FROM kinerja_jawaban k WHERE k.dibuat_pada >= $1 AND k.dibuat_pada < $2`+syarat, args...).Scan(&jumlah)
	return jumlah, err
}

// Terbaru mengambil satu halaman catatan, dari yang paling baru; lewati adalah jumlah catatan di halaman-halaman sebelumnya
func (r *KinerjaRepository) Terbaru(sejak, sampai time.Time, akun string, batas, lewati int) ([]model.Kinerja, error) {
	syarat, args := saringAkun(akun, []any{sejak, sampai, batas, lewati})
	rows, err := r.db.Query(`SELECT k.profil, k.berhasil, k.galat, k.lama_ms, k.token_masuk, k.token_keluar, k.panggilan_llm, k.alat,
			k.panjang_jawaban, k.dibuat_pada, `+kunciAkun+`, CASE WHEN k.jenis_akun = 'tamu' THEN '' ELSE COALESCE(p.nama, '') END
		FROM kinerja_jawaban k LEFT JOIN pengguna p ON p.id = k.pengguna_id
		WHERE k.dibuat_pada >= $1 AND k.dibuat_pada < $2`+syarat+` ORDER BY k.dibuat_pada DESC LIMIT $3 OFFSET $4`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	daftar := []model.Kinerja{}
	for rows.Next() {
		var k model.Kinerja
		var alat string
		if err := rows.Scan(&k.Profil, &k.Berhasil, &k.Galat, &k.LamaMs, &k.TokenMasuk, &k.TokenKeluar, &k.PanggilanLLM, &alat, &k.PanjangJawaban, &k.DibuatPada,
			&k.Akun, &k.NamaAkun); err != nil {
			return nil, err
		}
		k.Alat = []string{}
		if alat != "" {
			k.Alat = strings.Split(alat, ",")
		}
		daftar = append(daftar, k)
	}
	return daftar, rows.Err()
}

// Penilaian menghitung suka dan tidak suka di rentang waktu; baris pertama total, lalu per profil; akun kosong = semua akun
func (r *KinerjaRepository) Penilaian(sejak, sampai time.Time, akun string) ([]model.PenilaianJawaban, error) {
	syarat, args := saringPesan(akun, []any{sejak, sampai})
	rows, err := r.db.Query(`SELECT COALESCE(p.profil, ''), COUNT(*) FILTER (WHERE p.penilaian = 1), COUNT(*) FILTER (WHERE p.penilaian = -1)
		FROM pesan p WHERE p.penilaian IS NOT NULL AND p.dinilai_pada >= $1 AND p.dinilai_pada < $2`+syarat+`
		GROUP BY ROLLUP(p.profil) ORDER BY GROUPING(p.profil) DESC, COUNT(*) DESC`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	daftar := []model.PenilaianJawaban{}
	for rows.Next() {
		var p model.PenilaianJawaban
		if err := rows.Scan(&p.Profil, &p.Suka, &p.TidakSuka); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// TidakDisukai mengambil jawaban terbaru yang tidak disukai beserta pertanyaan tepat sebelumnya, dipotong pendek
func (r *KinerjaRepository) TidakDisukai(sejak, sampai time.Time, akun string, batas int) ([]model.JawabanDinilai, error) {
	syarat, args := saringPesan(akun, []any{sejak, sampai, batas})
	rows, err := r.db.Query(`SELECT p.profil, COALESCE(LEFT(t.isi, 200), ''), LEFT(p.isi, 300), p.dinilai_pada
		FROM pesan p LEFT JOIN LATERAL (
			SELECT isi FROM pesan WHERE percakapan_id = p.percakapan_id AND urutan < p.urutan AND pengirim = 'user'
			ORDER BY urutan DESC LIMIT 1
		) AS t ON TRUE
		WHERE p.penilaian = -1 AND p.dinilai_pada >= $1 AND p.dinilai_pada < $2`+syarat+` ORDER BY p.dinilai_pada DESC LIMIT $3`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	daftar := []model.JawabanDinilai{}
	for rows.Next() {
		var j model.JawabanDinilai
		if err := rows.Scan(&j.Profil, &j.Pertanyaan, &j.Jawaban, &j.DinilaiPada); err != nil {
			return nil, err
		}
		daftar = append(daftar, j)
	}
	return daftar, rows.Err()
}
