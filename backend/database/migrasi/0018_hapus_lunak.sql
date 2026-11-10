-- hapus lunak: percakapan dan pesan yang dihapus pengguna hanya ditandai, bukan dibuang, agar penilaian di halaman
-- kinerja dan datanya tetap ada; NULL = belum dihapus. Pesan juga ditandai saat pertanyaan diedit atau jawaban dibuat ulang
ALTER TABLE percakapan ADD COLUMN IF NOT EXISTS dihapus_pada TIMESTAMPTZ;
ALTER TABLE pesan ADD COLUMN IF NOT EXISTS dihapus_pada TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS percakapan_aktif ON percakapan (pengguna_id) WHERE dihapus_pada IS NULL;
