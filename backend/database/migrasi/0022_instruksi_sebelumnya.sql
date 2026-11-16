-- versi instruksi pribadi sebelum diubah lewat chat, untuk tombol batalkan
ALTER TABLE pengguna ADD COLUMN IF NOT EXISTS instruksi_sebelumnya TEXT NOT NULL DEFAULT '';
