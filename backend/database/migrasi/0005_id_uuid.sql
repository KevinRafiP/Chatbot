DROP TABLE IF EXISTS pesan, percakapan, sesi_login, pengguna;

CREATE TABLE pengguna (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nama        TEXT NOT NULL,
    jenis       TEXT NOT NULL DEFAULT 'tamu',
    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sesi_login (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pengguna_id      UUID NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    token_hash       TEXT NOT NULL UNIQUE,
    perangkat        TEXT NOT NULL DEFAULT '',
    dibuat_pada      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    terakhir_dipakai TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kedaluwarsa_pada TIMESTAMPTZ NOT NULL
);

CREATE TABLE percakapan (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pengguna_id     UUID NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    judul           TEXT NOT NULL DEFAULT 'Percakapan baru',
    dibuat_pada     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    diperbarui_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pesan (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    urutan        BIGSERIAL,
    percakapan_id UUID NOT NULL REFERENCES percakapan(id) ON DELETE CASCADE,
    pengirim      TEXT NOT NULL CHECK (pengirim IN ('user', 'asisten')),
    isi           TEXT NOT NULL,
    sumber        TEXT NOT NULL DEFAULT '',
    dibuat_pada   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sesi_login_pengguna ON sesi_login (pengguna_id);
CREATE INDEX idx_percakapan_pengguna ON percakapan (pengguna_id, diperbarui_pada DESC);
CREATE INDEX idx_pesan_percakapan ON pesan (percakapan_id, urutan);