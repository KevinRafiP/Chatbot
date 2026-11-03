-- percakapan yang disematkan tampil paling atas; NULL = tidak disematkan
ALTER TABLE percakapan ADD COLUMN IF NOT EXISTS disematkan_pada TIMESTAMPTZ;

-- penilaian pengguna untuk jawaban asisten: 1 = suka, -1 = tidak suka, NULL = belum dinilai;
-- profil (cepat, mendalam) disimpan agar penilaian bisa dibandingkan per profil di halaman kinerja
ALTER TABLE pesan ADD COLUMN IF NOT EXISTS penilaian SMALLINT CHECK (penilaian IN (-1, 1));
ALTER TABLE pesan ADD COLUMN IF NOT EXISTS dinilai_pada TIMESTAMPTZ;
ALTER TABLE pesan ADD COLUMN IF NOT EXISTS profil TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS pesan_dinilai_pada ON pesan (dinilai_pada) WHERE penilaian IS NOT NULL;