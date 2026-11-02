-- kinerja_jawaban: lama, token, dan alat setiap jawaban AI untuk halaman kinerja admin;
-- isi pertanyaan dan jawaban sengaja tidak disimpan
CREATE TABLE kinerja_jawaban (
    id              BIGSERIAL PRIMARY KEY,
    profil          TEXT NOT NULL,
    berhasil        BOOLEAN NOT NULL,
    galat           TEXT NOT NULL DEFAULT '',
    lama_ms         INTEGER NOT NULL,
    token_masuk     INTEGER NOT NULL DEFAULT 0,
    token_keluar    INTEGER NOT NULL DEFAULT 0,
    panggilan_llm   INTEGER NOT NULL DEFAULT 0,
    alat            TEXT NOT NULL DEFAULT '',
    panjang_jawaban INTEGER NOT NULL DEFAULT 0,
    dibuat_pada     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kinerja_jawaban_waktu ON kinerja_jawaban (dibuat_pada);
