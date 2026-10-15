-- favorit: pesan yang ditandai bintang oleh pemilik percakapan
ALTER TABLE pesan ADD COLUMN favorit BOOLEAN NOT NULL DEFAULT FALSE;