-- akun yang bertanya, agar admin bisa melihat kinerja per akun; tamu dihapus saat sesinya habis,
-- jadi jenis akun ikut disimpan dan pengguna_id menjadi NULL tanpa menghapus catatannya
ALTER TABLE kinerja_jawaban ADD COLUMN IF NOT EXISTS pengguna_id UUID REFERENCES pengguna(id) ON DELETE SET NULL;
ALTER TABLE kinerja_jawaban ADD COLUMN IF NOT EXISTS jenis_akun TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_kinerja_jawaban_pengguna ON kinerja_jawaban (pengguna_id);