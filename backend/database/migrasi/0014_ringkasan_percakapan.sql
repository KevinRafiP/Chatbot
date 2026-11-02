-- ringkasan: rangkuman pesan lama percakapan panjang, agar AI tetap ingat awal percakapan tanpa membaca semua pesan
-- ringkasan_sampai: urutan pesan terakhir yang sudah masuk ringkasan; pesan sesudahnya tetap dikirim utuh
ALTER TABLE percakapan ADD COLUMN ringkasan TEXT NOT NULL DEFAULT '',
    ADD COLUMN ringkasan_sampai BIGINT NOT NULL DEFAULT 0;
