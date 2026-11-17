import json
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from alat.catatan import kunci
from llm import pemakaian
from pengaman.teks import bersihkan_data
from prompt import instruksi_pribadi

# hasil pencarian sering berbahasa lain; pengingat pendek ini menjaga bahasa jawaban tetap mengikuti pertanyaan
ALAT_BACA_WEB = {"cari_web", "baca_url", "wikipedia"}
PENGINGAT_BAHASA = ("Pengingat: tulis seluruh jawaban, termasuk judul bagian dan isi tabel, dengan bahasa pertanyaan terakhir pengguna; "
                    "terjemahkan isi sumber yang berbahasa lain.")

# alat yang menulis ke browser pengguna atau mengubah instruksi pribadi dijalankan satu per satu di benang utama
ALAT_BERURUTAN = {"jalankan_python", "ubah_instruksi"}
MAKS_ALAT_BERSAMAAN = 6
MAKS_KETERANGAN = 3

PESAN_PUTARAN_TERAKHIR = (
    "Batas pencarian sudah tercapai. Jangan memanggil alat lagi. "
    "Jawab sekarang hanya dari informasi yang sudah terkumpul; "
    "jika belum cukup, katakan bagian mana yang tidak ditemukan."
)


def buat_aksi(kotak_alat, maks_langkah):
    """Simpul yang menjalankan alat yang diminta LLM lalu menyimpan hasilnya ke percakapan."""

    def aksi(keadaan):
        panggilan = keadaan["panggilan"]
        for p in panggilan:
            logging.info("agen memanggil alat %s %s", p.get("name"), json.dumps(p.get("input") or {}, ensure_ascii=False)[:200])
            keadaan.setdefault("alat_dipakai", []).append(str(p.get("name", "")))
        if keadaan.get("kabar"):
            keadaan["kabar"]("status", {"teks": gabung_keterangan(panggilan, kotak_alat)})

        balasan = []
        for p, hasil in zip(panggilan, jalankan_bersamaan(kotak_alat, panggilan, keadaan["catatan"])):
            balasan.append({
                "toolResult": {
                    "toolUseId": p.get("toolUseId", ""),
                    "content": [{"text": json.dumps(bersihkan_data(hasil), ensure_ascii=False)}],
                }
            })

        if any(p.get("name") in ALAT_BACA_WEB for p in keadaan["panggilan"]):
            balasan.append({"text": PENGINGAT_BAHASA})
        if keadaan["putaran_llm"] >= maks_langkah - 1:
            balasan.append({"text": PESAN_PUTARAN_TERAKHIR})

        keadaan["isi"].append({"role": "user", "content": balasan})
        pakai_instruksi_baru(keadaan)
        return keadaan

    return aksi

def jalankan_bersamaan(kotak_alat, panggilan, catatan):
    """Alat dijalankan bersamaan, jadi lama menunggunya sama dengan alat yang paling lama, bukan jumlah semuanya.
    Urutan hasil tetap sama dengan urutan panggilan."""
    def satu(p):
        return kotak_alat.jalankan(p.get("name", ""), p.get("input") or {}, catatan)

    kunci(catatan)
    hasil = [None] * len(panggilan)
    bersamaan = [i for i, p in enumerate(panggilan) if p.get("name") not in ALAT_BERURUTAN]
    if len(bersamaan) > 1:
        token = pemakaian.bawa()

        def di_benang(p):
            pemakaian.pasang(token)
            return satu(p)

        with ThreadPoolExecutor(max_workers=min(len(bersamaan), MAKS_ALAT_BERSAMAAN)) as pelaksana:
            for i, isi in zip(bersamaan, pelaksana.map(di_benang, [panggilan[i] for i in bersamaan])):
                hasil[i] = isi
    for i, p in enumerate(panggilan):
        if hasil[i] is None:
            hasil[i] = satu(p)
    return hasil

def pakai_instruksi_baru(keadaan):
    """Setelah ubah_instruksi berhasil, bagian instruksi pribadi di prompt diganti agar jawaban ini sudah memakai instruksi baru."""
    baru = keadaan["catatan"].get("instruksi")
    if not baru:
        return
    bagian = instruksi_pribadi(baru["teks"])
    lama = keadaan.get("bagian_pribadi") or ""
    tambahan = keadaan.get("instruksi_tambahan", "")
    keadaan["instruksi_tambahan"] = tambahan.replace(lama, bagian) if lama and lama in tambahan else tambahan + bagian
    keadaan["bagian_pribadi"] = bagian

def gabung_keterangan(panggilan, kotak_alat):
    keterangan = list(dict.fromkeys(keterangan_alat(p, kotak_alat) for p in panggilan))
    teks = " · ".join(keterangan[:MAKS_KETERANGAN])
    return teks + (f" (+{len(keterangan) - MAKS_KETERANGAN} lagi)" if len(keterangan) > MAKS_KETERANGAN else "")

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
    if panggilan.get("name") == "ubah_instruksi":
        return "Memperbarui instruksi pribadi"
    if panggilan.get("name") == "cari_gambar":
        return f"Mencari gambar: {str(masukan.get('kueri', ''))[:80]}"
    return kotak_alat.keterangan(panggilan.get("name")) if kotak_alat else "Menjalankan alat"