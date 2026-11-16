-- instruksi pribadi: cara menjawab yang diinginkan pengguna (nama panggilan, gaya, bahasa), selalu dikirim ke agent
ALTER TABLE pengguna ADD COLUMN IF NOT EXISTS instruksi_pribadi TEXT NOT NULL DEFAULT '';
