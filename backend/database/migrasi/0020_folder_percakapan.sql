-- folder untuk mengelompokkan percakapan; folder yang dihapus tidak menghapus percakapannya, hanya mengeluarkannya
CREATE TABLE IF NOT EXISTS folder (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pengguna_id UUID NOT NULL REFERENCES pengguna(id) ON DELETE CASCADE,
    nama        TEXT NOT NULL,
    dibuat_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_folder_pengguna ON folder (pengguna_id);

ALTER TABLE percakapan ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES folder(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_percakapan_folder ON percakapan (folder_id) WHERE folder_id IS NOT NULL;
