package repository

import (
	"database/sql"
	"encoding/json"
	"errors"
	"strings"
	"unicode/utf8"

	"chatbot/backend/model"
)

type PercakapanRepository struct {
	db *sql.DB
}

func BaruPercakapanRepository(db *sql.DB) *PercakapanRepository {
	return &PercakapanRepository{db: db}
}

// Semua mengambil percakapan milik satu pengguna: yang disematkan paling atas (terakhir disematkan dulu), lalu yang terbaru
func (r *PercakapanRepository) Semua(penggunaID string) ([]model.Percakapan, error) {
	rows, err := r.db.Query(`SELECT id, judul, disematkan_pada IS NOT NULL, diperbarui_pada FROM percakapan
		WHERE pengguna_id = $1 AND dihapus_pada IS NULL ORDER BY disematkan_pada DESC NULLS LAST, diperbarui_pada DESC`, penggunaID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Percakapan{}
	for rows.Next() {
		var p model.Percakapan
		if err := rows.Scan(&p.ID, &p.Judul, &p.Disematkan, &p.DiperbaruiPada); err != nil {
			return nil, err
		}
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// Buat membuat percakapan kosong untuk satu pengguna
func (r *PercakapanRepository) Buat(penggunaID string) (model.Percakapan, error) {
	var p model.Percakapan
	err := r.db.QueryRow(`INSERT INTO percakapan (pengguna_id) VALUES ($1)
		RETURNING id, judul, diperbarui_pada`, penggunaID).Scan(&p.ID, &p.Judul, &p.DiperbaruiPada)
	return p, err
}

// Milik memeriksa apakah percakapan itu ada, belum dihapus, dan dimiliki pengguna tersebut
func (r *PercakapanRepository) Milik(id, penggunaID string) (bool, error) {
	var ada bool
	err := r.db.QueryRow(`SELECT EXISTS(SELECT 1 FROM percakapan WHERE id = $1 AND pengguna_id = $2 AND dihapus_pada IS NULL)`,
		id, penggunaID).Scan(&ada)
	return ada, err
}

// Hapus menyembunyikan percakapan milik pengguna tanpa membuang barisnya (hapus lunak), agar pesan, penilaian,
// dan catatan kinerjanya tetap ada untuk halaman kinerja admin
func (r *PercakapanRepository) Hapus(id, penggunaID string) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE percakapan SET dihapus_pada = NOW() WHERE id = $1 AND pengguna_id = $2 AND dihapus_pada IS NULL`, id, penggunaID)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// UbahJudul mengganti judul percakapan
func (r *PercakapanRepository) UbahJudul(id string, judul string) error {
	_, err := r.db.Exec(`UPDATE percakapan SET judul = $1 WHERE id = $2`, judul, id)
	return err
}

// GantiJudul mengganti judul percakapan milik pengguna; sql.ErrNoRows bila percakapan tidak ada
func (r *PercakapanRepository) GantiJudul(id, penggunaID, judul string) (model.Percakapan, error) {
	var p model.Percakapan
	err := r.db.QueryRow(`UPDATE percakapan SET judul = $1 WHERE id = $2 AND pengguna_id = $3 AND dihapus_pada IS NULL
		RETURNING id, judul, disematkan_pada IS NOT NULL, diperbarui_pada`, judul, id, penggunaID).Scan(&p.ID, &p.Judul, &p.Disematkan, &p.DiperbaruiPada)
	return p, err
}

// Sematkan menyematkan atau melepas sematan percakapan milik pengguna; false bila percakapan tidak ada
func (r *PercakapanRepository) Sematkan(id, penggunaID string, sematkan bool) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE percakapan SET disematkan_pada = CASE WHEN $3 THEN NOW() END
		WHERE id = $1 AND pengguna_id = $2 AND dihapus_pada IS NULL`, id, penggunaID, sematkan)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// DaftarPesan mengambil pesan sebuah percakapan dari yang paling lama; batas 0 berarti semua, selain itu hanya N terakhir
func (r *PercakapanRepository) DaftarPesan(percakapanID string, batas int) ([]model.Pesan, error) {
	return r.DaftarPesanSetelah(percakapanID, 0, batas)
}

// DaftarPesanSetelah sama seperti DaftarPesan, tetapi hanya pesan sesudah urutan tertentu (yang belum diringkas)
func (r *PercakapanRepository) DaftarPesanSetelah(percakapanID string, setelah int64, batas int) ([]model.Pesan, error) {
	rows, err := r.db.Query(`SELECT id, urutan, pengirim, isi, sumber, favorit, COALESCE(penilaian, 0), lampiran_nama, dibuat_pada FROM (
		SELECT id, urutan, pengirim, isi, sumber, favorit, penilaian, lampiran_nama, dibuat_pada FROM pesan
			WHERE percakapan_id = $1 AND urutan > $3 AND dihapus_pada IS NULL ORDER BY urutan DESC LIMIT NULLIF($2, 0)
		) AS terakhir ORDER BY urutan`, percakapanID, batas, setelah)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.Pesan{}
	for rows.Next() {
		var p model.Pesan
		var sumber string
		if err := rows.Scan(&p.ID, &p.Urutan, &p.Pengirim, &p.Isi, &sumber, &p.Favorit, &p.Penilaian, &p.Lampiran, &p.DibuatPada); err != nil {
			return nil, err
		}
		p.Sumber = pecahSumber(sumber)
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// Ringkasan mengambil ringkasan percakapan dan urutan pesan terakhir yang sudah masuk ringkasan
func (r *PercakapanRepository) Ringkasan(id string) (string, int64, error) {
	var ringkasan string
	var sampai int64
	err := r.db.QueryRow(`SELECT ringkasan, ringkasan_sampai FROM percakapan WHERE id = $1`, id).Scan(&ringkasan, &sampai)
	return ringkasan, sampai, err
}

// SimpanRingkasan menyimpan ringkasan baru hanya bila belum ada proses lain yang menyimpan lebih dulu
func (r *PercakapanRepository) SimpanRingkasan(id, ringkasan string, sampaiBaru, sampaiLama int64) error {
	_, err := r.db.Exec(`UPDATE percakapan SET ringkasan = $2, ringkasan_sampai = $3 WHERE id = $1 AND ringkasan_sampai = $4`,
		id, ringkasan, sampaiBaru, sampaiLama)
	return err
}

// SimpanPesan menyimpan satu pesan beserta sumbernya dan memperbarui waktu percakapannya
func (r *PercakapanRepository) SimpanPesan(percakapanID string, pengirim, isi string, sumber []model.Sumber) (model.Pesan, error) {
	return r.SimpanPesanLampiran(percakapanID, pengirim, isi, sumber, model.Lampiran{})
}

// SimpanPesanLampiran sama seperti SimpanPesan, ditambah berkas yang diunggah bersama pesan itu
func (r *PercakapanRepository) SimpanPesanLampiran(percakapanID string, pengirim, isi string, sumber []model.Sumber, lampiran model.Lampiran) (model.Pesan, error) {
	if sumber == nil {
		sumber = []model.Sumber{}
	}
	teksSumber, err := json.Marshal(sumber)
	if err != nil {
		return model.Pesan{}, err
	}

	p := model.Pesan{Pengirim: pengirim, Isi: isi, Sumber: sumber, Lampiran: lampiran.Nama}
	err = r.db.QueryRow(`INSERT INTO pesan (percakapan_id, pengirim, isi, sumber, lampiran_nama, lampiran_teks) VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING id, dibuat_pada`, percakapanID, pengirim, isi, string(teksSumber), lampiran.Nama, lampiran.Teks).Scan(&p.ID, &p.DibuatPada)
	if err != nil {
		return model.Pesan{}, err
	}
	_, err = r.db.Exec(`UPDATE percakapan SET diperbarui_pada = NOW() WHERE id = $1`, percakapanID)
	return p, err
}

// SimpanTanyaJawab menyimpan pertanyaan dan jawabannya sekaligus dalam satu transaksi, jadi pertanyaan yang gagal
// atau dihentikan tidak pernah tersimpan tanpa jawaban; profil dicatat pada jawaban untuk penilaian per profil
func (r *PercakapanRepository) SimpanTanyaJawab(percakapanID, pertanyaan string, lampiran model.Lampiran, jawaban string, sumber []model.Sumber, profil string) (model.Pesan, model.Pesan, error) {
	if sumber == nil {
		sumber = []model.Sumber{}
	}
	teksSumber, err := json.Marshal(sumber)
	if err != nil {
		return model.Pesan{}, model.Pesan{}, err
	}

	tx, err := r.db.Begin()
	if err != nil {
		return model.Pesan{}, model.Pesan{}, err
	}
	defer tx.Rollback()

	tanya := model.Pesan{Pengirim: "user", Isi: pertanyaan, Sumber: []model.Sumber{}, Lampiran: lampiran.Nama}
	err = tx.QueryRow(`INSERT INTO pesan (percakapan_id, pengirim, isi, sumber, lampiran_nama, lampiran_teks) VALUES ($1, 'user', $2, '[]', $3, $4)
		RETURNING id, dibuat_pada`, percakapanID, pertanyaan, lampiran.Nama, lampiran.Teks).Scan(&tanya.ID, &tanya.DibuatPada)
	if err != nil {
		return model.Pesan{}, model.Pesan{}, err
	}
	jawab := model.Pesan{Pengirim: "asisten", Isi: jawaban, Sumber: sumber}
	err = tx.QueryRow(`INSERT INTO pesan (percakapan_id, pengirim, isi, sumber, profil) VALUES ($1, 'asisten', $2, $3, $4)
		RETURNING id, dibuat_pada`, percakapanID, jawaban, string(teksSumber), profil).Scan(&jawab.ID, &jawab.DibuatPada)
	if err != nil {
		return model.Pesan{}, model.Pesan{}, err
	}
	if _, err := tx.Exec(`UPDATE percakapan SET diperbarui_pada = NOW() WHERE id = $1`, percakapanID); err != nil {
		return model.Pesan{}, model.Pesan{}, err
	}
	return tanya, jawab, tx.Commit()
}

// LampiranTerakhir mengambil berkas terbaru di antara batas pesan terakhir sebuah percakapan;
// kosong bila tidak ada, agar berkas lama tidak terus ikut ke pertanyaan yang sudah jauh
func (r *PercakapanRepository) LampiranTerakhir(percakapanID string, batas int) (model.Lampiran, error) {
	var l model.Lampiran
	err := r.db.QueryRow(`SELECT lampiran_nama, lampiran_teks FROM (
			SELECT lampiran_nama, lampiran_teks, urutan FROM pesan WHERE percakapan_id = $1 AND dihapus_pada IS NULL ORDER BY urutan DESC LIMIT $2
		) AS terakhir WHERE lampiran_nama <> '' ORDER BY urutan DESC LIMIT 1`, percakapanID, batas).Scan(&l.Nama, &l.Teks)
	if errors.Is(err, sql.ErrNoRows) {
		return model.Lampiran{}, nil
	}
	return l, err
}

// UbahFavorit menandai atau melepas bintang sebuah pesan, hanya bila percakapannya milik pengguna itu
func (r *PercakapanRepository) UbahFavorit(pesanID, penggunaID string, favorit bool) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE pesan p SET favorit = $3 FROM percakapan c
		WHERE p.id = $1 AND p.percakapan_id = c.id AND c.pengguna_id = $2 AND p.dihapus_pada IS NULL AND c.dihapus_pada IS NULL`, pesanID, penggunaID, favorit)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// UbahPenilaian menyimpan suka (1), tidak suka (-1), atau menghapus penilaian (0) pada jawaban asisten milik pengguna
func (r *PercakapanRepository) UbahPenilaian(pesanID, penggunaID string, nilai int) (bool, error) {
	hasil, err := r.db.Exec(`UPDATE pesan p SET penilaian = NULLIF($3::SMALLINT, 0), dinilai_pada = CASE WHEN $3 = 0 THEN NULL ELSE NOW() END
		FROM percakapan c WHERE p.id = $1 AND p.percakapan_id = c.id AND c.pengguna_id = $2 AND p.pengirim = 'asisten'
			AND p.dihapus_pada IS NULL AND c.dihapus_pada IS NULL`,
		pesanID, penggunaID, nilai)
	if err != nil {
		return false, err
	}
	jumlah, err := hasil.RowsAffected()
	return jumlah > 0, err
}

// DaftarFavorit mengambil pesan berbintang dari semua percakapan milik pengguna, yang terbaru di atas
func (r *PercakapanRepository) DaftarFavorit(penggunaID string, batas int) ([]model.PesanFavorit, error) {
	rows, err := r.db.Query(`SELECT p.id, p.pengirim, p.isi, p.sumber, p.dibuat_pada, c.id, c.judul
		FROM pesan p JOIN percakapan c ON c.id = p.percakapan_id
		WHERE c.pengguna_id = $1 AND p.favorit AND p.dihapus_pada IS NULL AND c.dihapus_pada IS NULL ORDER BY p.dibuat_pada DESC LIMIT $2`, penggunaID, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.PesanFavorit{}
	for rows.Next() {
		var p model.PesanFavorit
		var sumber string
		if err := rows.Scan(&p.ID, &p.Pengirim, &p.Isi, &sumber, &p.DibuatPada, &p.PercakapanID, &p.JudulPercakapan); err != nil {
			return nil, err
		}
		p.Sumber = pecahSumber(sumber)
		p.Favorit = true
		daftar = append(daftar, p)
	}
	return daftar, rows.Err()
}

// HapusPesanMulai menyembunyikan pertanyaan pengguna pesanID dan semua pesan sesudahnya (hapus lunak), dipakai saat
// pertanyaan diedit atau jawabannya dibuat ulang; penilaian lamanya tetap terhitung di halaman kinerja.
// Ringkasan yang sudah memuat pesan itu dikosongkan agar dibuat ulang. Mengembalikan lampiran pertanyaan itu,
// atau sql.ErrNoRows bila pesan bukan pertanyaan yang masih tampil di percakapan ini
func (r *PercakapanRepository) HapusPesanMulai(percakapanID, pesanID string) (model.Lampiran, error) {
	tx, err := r.db.Begin()
	if err != nil {
		return model.Lampiran{}, err
	}
	defer tx.Rollback()

	var urutan int64
	var l model.Lampiran
	err = tx.QueryRow(`SELECT urutan, lampiran_nama, lampiran_teks FROM pesan
		WHERE id = $1 AND percakapan_id = $2 AND pengirim = 'user' AND dihapus_pada IS NULL`, pesanID, percakapanID).Scan(&urutan, &l.Nama, &l.Teks)
	if err != nil {
		return model.Lampiran{}, err
	}
	if _, err := tx.Exec(`UPDATE pesan SET dihapus_pada = NOW() WHERE percakapan_id = $1 AND urutan >= $2 AND dihapus_pada IS NULL`,
		percakapanID, urutan); err != nil {
		return model.Lampiran{}, err
	}
	if _, err := tx.Exec(`UPDATE percakapan SET ringkasan = '', ringkasan_sampai = 0, diperbarui_pada = NOW()
		WHERE id = $1 AND ringkasan_sampai >= $2`, percakapanID, urutan); err != nil {
		return model.Lampiran{}, err
	}
	return l, tx.Commit()
}

// Cari mencari percakapan milik pengguna yang judul atau isi pesannya memuat kueri, yang terbaru di atas.
// Cuplikan diambil dari pesan terbaru yang cocok; kosong bila hanya judulnya yang cocok
func (r *PercakapanRepository) Cari(penggunaID, kueri string, batas int) ([]model.HasilCari, error) {
	pola := "%" + strings.NewReplacer(`\`, `\\`, "%", `\%`, "_", `\_`).Replace(kueri) + "%"
	rows, err := r.db.Query(`SELECT c.id, c.judul, c.disematkan_pada IS NOT NULL, c.diperbarui_pada, COALESCE(m.isi, '')
		FROM percakapan c LEFT JOIN LATERAL (
			SELECT isi FROM pesan WHERE percakapan_id = c.id AND dihapus_pada IS NULL AND isi ILIKE $2
			ORDER BY urutan DESC LIMIT 1
		) AS m ON TRUE
		WHERE c.pengguna_id = $1 AND c.dihapus_pada IS NULL AND (c.judul ILIKE $2 OR m.isi IS NOT NULL)
		ORDER BY c.diperbarui_pada DESC LIMIT $3`, penggunaID, pola, batas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	daftar := []model.HasilCari{}
	for rows.Next() {
		var h model.HasilCari
		var isi string
		if err := rows.Scan(&h.ID, &h.Judul, &h.Disematkan, &h.DiperbaruiPada, &isi); err != nil {
			return nil, err
		}
		h.Cuplikan = cuplikan(isi, kueri, 60)
		daftar = append(daftar, h)
	}
	return daftar, rows.Err()
}

// cuplikan memotong teks di sekitar kata yang dicari, paling banyak sekitar dua kali sisi huruf
func cuplikan(teks, kueri string, sisi int) string {
	huruf := []rune(strings.Join(strings.Fields(teks), " "))
	if len(huruf) == 0 {
		return ""
	}
	kecil := strings.ToLower(string(huruf))
	awal := 0
	if letak := strings.Index(kecil, strings.ToLower(kueri)); letak > 0 {
		awal = max(utf8.RuneCountInString(kecil[:letak])-sisi, 0)
	}
	akhir := min(awal+sisi*2+len([]rune(kueri)), len(huruf))
	hasil := string(huruf[awal:akhir])
	if awal > 0 {
		hasil = "..." + hasil
	}
	if akhir < len(huruf) {
		hasil += "..."
	}
	return hasil
}

// pecahSumber membaca kolom sumber: bentuk baru berupa JSON, bentuk lama satu sumber per baris
func pecahSumber(teks string) []model.Sumber {
	daftar := []model.Sumber{}
	if strings.HasPrefix(teks, "[") && json.Unmarshal([]byte(teks), &daftar) == nil {
		return daftar
	}

	daftar = []model.Sumber{}
	for _, baris := range strings.Split(teks, "\n") {
		baris = strings.TrimSpace(baris)
		if baris == "" {
			continue
		}
		if strings.HasPrefix(baris, "http://") || strings.HasPrefix(baris, "https://") {
			daftar = append(daftar, model.Sumber{Judul: baris, URL: baris})
		} else {
			daftar = append(daftar, model.Sumber{Judul: baris})
		}
	}
	return daftar
}
