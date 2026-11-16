-- id akun Google (klaim "sub"), diisi saat pengguna pertama kali masuk dengan Google
ALTER TABLE pengguna ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE;
