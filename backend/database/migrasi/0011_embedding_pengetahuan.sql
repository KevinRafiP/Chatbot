-- satu data pengetahuan dipecah menjadi beberapa potongan untuk pencarian makna;
-- sidik = md5(judul + baris baru + isi) saat dipotong, jadi data yang berubah dikenali dan dipotong ulang
CREATE TABLE IF NOT EXISTS potongan_pengetahuan (
    id             BIGSERIAL PRIMARY KEY,
    pengetahuan_id INT NOT NULL REFERENCES pengetahuan(id) ON DELETE CASCADE,
    urutan         INT NOT NULL,
    isi            TEXT NOT NULL,
    sidik          TEXT NOT NULL,
    UNIQUE (pengetahuan_id, urutan)
);

-- tabel vektor butuh ekstensi pgvector (Neon sudah menyediakan); tanpa pgvector bagian ini dilewati
-- dan backend tetap memakai pencarian kata kunci
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        RAISE NOTICE 'pgvector belum terpasang, tabel embedding_potongan tidak dibuat';
        RETURN;
    END IF;

    CREATE EXTENSION IF NOT EXISTS vector;

    -- satu potongan bisa punya vektor dari beberapa model; kolom vektor sengaja tanpa ukuran
    -- agar model dengan dimensi lain bisa disimpan di tabel yang sama
    CREATE TABLE IF NOT EXISTS embedding_potongan (
        potongan_id BIGINT NOT NULL REFERENCES potongan_pengetahuan(id) ON DELETE CASCADE,
        model       TEXT NOT NULL,
        dimensi     INT NOT NULL,
        vektor      vector NOT NULL,
        dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (potongan_id, model),
        CHECK (vector_dims(vektor) = dimensi)
    );

    -- satu indeks HNSW per model; model baru cukup ditambah indeks serupa dengan dimensi dan namanya sendiri
    CREATE INDEX IF NOT EXISTS embedding_cohere_multilingual_v3 ON embedding_potongan
        USING hnsw ((vektor::vector(1024)) vector_cosine_ops)
        WHERE model = 'cohere.embed-multilingual-v3';
END $$;