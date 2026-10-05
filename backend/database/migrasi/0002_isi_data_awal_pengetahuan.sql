INSERT INTO pengetahuan (judul, isi, kata_kunci) VALUES
('Jam operasional', 'Kantor buka Senin sampai Jumat pukul 08.00 - 17.00 WIB. Sabtu dan Minggu libur.', 'jam buka operasional kantor libur'),
('Pendaftaran magang', 'Pendaftaran magang dilakukan lewat website Maganghub dengan mengunggah CV dan surat pengantar kampus.', 'daftar pendaftaran magang cv syarat'),
('Kontak admin', 'Admin dapat dihubungi lewat email admin@contoh.com atau WhatsApp 0812-0000-0000.', 'kontak admin email whatsapp hubungi')
ON CONFLICT (judul) DO NOTHING;