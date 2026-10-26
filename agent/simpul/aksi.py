import json
import logging
import urllib.parse

PESAN_PUTARAN_TERAKHIR = (
    "Batas pencarian sudah tercapai. Jangan memanggil alat lagi. "
    "Jawab sekarang hanya dari informasi yang sudah terkumpul; "
    "jika belum cukup, katakan bagian mana yang tidak ditemukan."
)


def buat_aksi(kotak_alat, maks_langkah):
    """Simpul yang menjalankan alat yang diminta LLM lalu menyimpan hasilnya ke percakapan."""

    def aksi(keadaan):
        balasan = []
        for p in keadaan["panggilan"]:
            logging.info("agen memanggil alat %s", p.get("name"))
            if keadaan.get("kabar"):
                keadaan["kabar"]("status", {"teks": keterangan_alat(p, kotak_alat)})
            hasil = kotak_alat.jalankan(p.get("name", ""), p.get("input") or {}, keadaan["catatan"])
            balasan.append({
                "toolResult": {
                    "toolUseId": p.get("toolUseId", ""),
                    "content": [{"text": json.dumps(hasil, ensure_ascii=False)}],
                }
            })

        if keadaan["putaran_llm"] >= maks_langkah - 1:
            balasan.append({"text": PESAN_PUTARAN_TERAKHIR})

        keadaan["isi"].append({"role": "user", "content": balasan})
        return keadaan

    return aksi

def keterangan_alat(panggilan, kotak_alat=None):
    """Kalimat singkat untuk pengguna tentang alat yang sedang dijalankan."""
    masukan = panggilan.get("input") or {}
    if panggilan.get("name") == "cari_web":
        return f"Mencari: {str(masukan.get('kueri', ''))[:80]}"
    if panggilan.get("name") == "baca_url":
        return f"Membaca: {urllib.parse.urlsplit(str(masukan.get('url', ''))).netloc}"
    if panggilan.get("name") == "hitung":
        return f"Menghitung: {str(masukan.get('ekspresi', ''))[:80]}"
    if panggilan.get("name") == "cari_pengetahuan":
        return f"Mencari data: {str(masukan.get('kueri', ''))[:80]}"
    if panggilan.get("name") == "wikipedia":
        return f"Membaca Wikipedia: {str(masukan.get('topik', ''))[:80]}"
    return kotak_alat.keterangan(panggilan.get("name")) if kotak_alat else "Menjalankan alat"