-- indeks HNSW untuk model embedding bawaan EMBED_PROVIDER api (Gemini Embedding 2, 768 dimensi)
-- dan local (bge-m3, 1024 dimensi); dilewati jika tabel embedding tidak ada karena pgvector belum terpasang
DO $$
BEGIN
    IF to_regclass('embedding_potongan') IS NULL THEN
        RETURN;
    END IF;

    CREATE INDEX IF NOT EXISTS embedding_gemini_2 ON embedding_potongan
        USING hnsw ((vektor::vector(768)) vector_cosine_ops)
        WHERE model = 'gemini-embedding-2';

    CREATE INDEX IF NOT EXISTS embedding_bge_m3 ON embedding_potongan
        USING hnsw ((vektor::vector(1024)) vector_cosine_ops)
        WHERE model = 'bge-m3';
END $$;