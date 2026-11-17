-- gambar dari internet di bawah jawaban: hanya alamat, judul, dan halaman asalnya (JSON); file gambarnya tidak disimpan
ALTER TABLE pesan ADD COLUMN IF NOT EXISTS gambar TEXT NOT NULL DEFAULT '[]';
