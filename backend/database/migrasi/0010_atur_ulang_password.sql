CREATE TABLE atur_ulang_password (
    token_hash       TEXT PRIMARY KEY,
    pengguna_id      UUID NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    dibuat_pada      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kedaluwarsa_pada TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_atur_ulang_password_pengguna ON atur_ulang_password (pengguna_id);