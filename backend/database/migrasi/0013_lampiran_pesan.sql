-- lampiran: teks berkas yang diunggah bersama pesan pengguna; isinya dipakai lagi untuk pertanyaan lanjutan
ALTER TABLE pesan ADD COLUMN lampiran_nama TEXT NOT NULL DEFAULT '',
    ADD COLUMN lampiran_teks TEXT NOT NULL DEFAULT '';