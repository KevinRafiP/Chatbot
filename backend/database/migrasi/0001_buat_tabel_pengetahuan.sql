CREATE TABLE IF NOT EXISTS pengetahuan (
    id          SERIAL PRIMARY KEY,
    judul       VARCHAR(200) NOT NULL,
    isi         TEXT NOT NULL,
    kata_kunci  TEXT NOT NULL DEFAULT '',
    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS pengetahuan_judul_unik ON pengetahuan (judul);