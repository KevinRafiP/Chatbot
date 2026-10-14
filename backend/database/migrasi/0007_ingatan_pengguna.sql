-- ingatan: ringkasan singkat tentang pengguna dari percakapan sebelumnya, dibaca agent sebagai memori jangka panjang
-- ingatan_hitung: jumlah pertanyaan sejak akun dibuat, dipakai untuk menentukan kapan ingatan diperbarui
ALTER TABLE pengguna ADD COLUMN ingatan TEXT NOT NULL DEFAULT '';
ALTER TABLE pengguna ADD COLUMN ingatan_hitung INT NOT NULL DEFAULT 0;
