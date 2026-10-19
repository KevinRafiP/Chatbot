ALTER TABLE pengguna ADD COLUMN email_terverifikasi BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE pengguna SET email_terverifikasi = TRUE WHERE email IS NOT NULL;

CREATE TABLE verifikasi_email (
    token_hash       TEXT PRIMARY KEY,
    pengguna_id      UUID NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    ingat            BOOLEAN NOT NULL DEFAULT TRUE,
    dibuat_pada      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kedaluwarsa_pada TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_verifikasi_email_pengguna ON verifikasi_email (pengguna_id);