-- gambar pesan yang sudah dihapus pengguna (pesannya atau percakapannya) tidak tampil lagi, jadi daftarnya dikosongkan
UPDATE pesan SET gambar = '[]'
WHERE gambar <> '[]' AND (dihapus_pada IS NOT NULL OR percakapan_id IN (SELECT id FROM percakapan WHERE dihapus_pada IS NOT NULL));
