import unicodedata

# Karakter tak terlihat bisa menyembunyikan perintah dari mata manusia tetapi tetap dibaca model,
# atau memecah kata agar lolos dari pola pengaman. Kode ditulis sebagai angka agar tidak ada karakter tersembunyi di berkas ini.
# ZWJ (200D) dan pemilih tampilan emoji (FE0E, FE0F) dibiarkan karena dipakai emoji gabungan
RENTANG_DIBUANG = (
    (0x0000, 0x0008), (0x000B, 0x000C), (0x000E, 0x001F), (0x007F, 0x009F),  # kontrol, kecuali tab dan baris baru
    (0x00AD, 0x00AD),  # tanda pemenggalan lunak
    (0x061C, 0x061C),  # penanda huruf Arab
    (0x180E, 0x180E),  # pemisah vokal Mongolia
    (0x200B, 0x200C),  # spasi lebar nol dan pemutus sambungan
    (0x200E, 0x200F),  # penanda arah kiri-kanan
    (0x202A, 0x202E),  # penanam dan pembalik arah teks
    (0x2060, 0x2064),  # penyambung kata dan operator tak terlihat
    (0x2066, 0x2069),  # isolat arah teks
    (0xFE00, 0xFE0D),  # pemilih variasi
    (0xFEFF, 0xFEFF),  # BOM
    (0xE0000, 0xE007F),  # karakter tag
    (0xE0100, 0xE01EF),  # pemilih variasi tambahan
)
# spasi khusus (spasi tak putus, spasi lebar tertentu) disamakan dengan spasi biasa
RENTANG_SPASI = ((0x00A0, 0x00A0), (0x2000, 0x200A), (0x202F, 0x202F), (0x205F, 0x205F), (0x3000, 0x3000))

TABEL_BERSIH = {kode: None for awal, akhir in RENTANG_DIBUANG for kode in range(awal, akhir + 1)}
TABEL_BERSIH.update({kode: " " for awal, akhir in RENTANG_SPASI for kode in range(awal, akhir + 1)})


def bersihkan_tak_terlihat(teks):
    """Membuang karakter tak terlihat dan kontrol dari pesan, berkas, dan halaman web sebelum dibaca model."""
    if not isinstance(teks, str) or not teks:
        return teks
    teks = teks.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", teks.translate(TABEL_BERSIH))


def bersihkan_data(data):
    """bersihkan_tak_terlihat untuk semua teks di dalam dict, list, atau tuple, misalnya hasil alat dan riwayat."""
    if isinstance(data, str):
        return bersihkan_tak_terlihat(data)
    if isinstance(data, dict):
        return {kunci: bersihkan_data(nilai) for kunci, nilai in data.items()}
    if isinstance(data, (list, tuple)):
        return type(data)(bersihkan_data(nilai) for nilai in data)
    return data
