import logging
import re

from llm.client import GalatLLM

POLA_SITASI = re.compile(r"\s*\[(?:data internal|sumber|source)?\s*(\d+)\]", re.IGNORECASE)


def jawab(keadaan):
    """Simpul akhir normal: mengambil teks jawaban dari LLM lalu merapikannya."""
    bagian = keadaan["konten_terakhir"].get("content", [])
    teks = "".join(b.get("text", "") for b in bagian).strip()
    keadaan["hasil"] = hasil(keadaan, teks or "Maaf, saya belum bisa menjawab itu.")
    return keadaan

JAWABAN_BATAS = "Maaf, saya belum menemukan jawabannya dalam batas pencarian. Coba pertanyaan yang lebih spesifik."
PESAN_JAWAB_SEKARANG = (
    "Batas pencarian sudah tercapai dan alat tidak bisa dipakai lagi. Jawab pertanyaan terakhir pengguna sekarang "
    "hanya dari informasi di atas. Jika belum cukup, sebut singkat bagian yang tidak ditemukan, lalu beri penjelasan umum."
)


def buat_batas(klien, instruksi):
    """Simpul saat putaran LLM habis: model diminta menjawab sekali lagi tanpa alat dari semua yang sudah terkumpul."""

    def batas(keadaan):
        kabar = keadaan.get("kabar")
        if kabar:
            kabar("status", {"teks": "Menyusun jawaban"})
        bahan = f"{gabung_percakapan(keadaan['isi'])}\n\n{PESAN_JAWAB_SEKARANG}"
        saat_teks = (lambda potongan: kabar("teks", {"teks": potongan})) if kabar else None
        try:
            konten = klien.kirim(instruksi, [{"role": "user", "content": [{"text": bahan}]}], None, False, saat_teks)
        except GalatLLM as galat:
            logging.warning("jawaban di batas pencarian gagal: %s", galat)
            konten = {}
        if not "".join(b.get("text", "") for b in konten.get("content", [])).strip():
            konten = {"role": "assistant", "content": [{"text": JAWABAN_BATAS}]}
        keadaan["konten_terakhir"] = konten
        return keadaan

    return batas

def gabung_percakapan(isi):
    """Percakapan berisi alat dijadikan satu teks biasa, karena Bedrock menolak blok alat tanpa daftar alat."""
    potongan = []
    for pesan in isi:
        blok = pesan.get("content", [])
        if pesan.get("role") == "assistant":
            if not any("toolUse" in b for b in blok):
                potongan += [f"Asisten: {b['text']}" for b in blok if b.get("text")]
            continue
        for b in blok:
            if b.get("text"):
                potongan.append(b["text"])
            for hasil_alat in b.get("toolResult", {}).get("content", []):
                potongan.append(f"Hasil alat: {hasil_alat.get('text', '')}")
    return "\n\n".join(potongan)

def tolak(keadaan):
    """Simpul akhir untuk permintaan yang ditolak pengaman; LLM tidak dipanggil sama sekali."""
    keadaan["hasil"] = {
        "jawaban": "Maaf, saya tidak bisa membantu permintaan itu. Saya hanya bisa menjawab pertanyaan dan mencari informasi.",
        "sumber": [],
        "pakai_internet": False,
    }
    return keadaan

POLA_DAFTAR_SUMBER = re.compile(r"\n\s*(?:sumber(?: referensi)?|referensi|rujukan)\s*:.*\Z", re.IGNORECASE | re.DOTALL)

ISTILAH = r"(?:data internal|catatan saya|ingatan saya)(?:\s+(?:yang\s+)?(?:tersedia|ada|saya miliki|saya punya|kami))?"
# "Dari data internal yang tersedia, Kevin ..." di awal kalimat
POLA_PEMBUKA_INTERNAL = re.compile(rf"(^|(?<=[.!?]\s)|(?<=\n))(?:dari|berdasarkan|menurut|sesuai(?: dengan)?|di|dalam)\s+{ISTILAH}\s*,\s*(\w)", re.IGNORECASE | re.MULTILINE)
# "... tentang X dalam data internal yang tersedia." di akhir kalimat atau anak kalimat
POLA_KETERANGAN_INTERNAL = re.compile(rf"\s+(?:dari|berdasarkan|menurut|di|dalam)\s+{ISTILAH}(?=[.,!?;:\n]|$)", re.IGNORECASE)

def hapus_istilah_internal(teks):
    """Membuang frasa yang menyebut data internal atau catatan, karena asal jawaban tidak boleh ditampilkan."""
    teks = POLA_PEMBUKA_INTERNAL.sub(lambda c: c.group(1) + c.group(2).upper(), teks)
    teks = POLA_KETERANGAN_INTERNAL.sub("", teks)
    return re.sub(r"\b(d)ata internal\b", lambda c: f"{c.group(1)}ata yang saya punya", teks, flags=re.IGNORECASE)
def hasil(keadaan, teks):
    catatan = keadaan["catatan"]
    semua = catatan["sumber"]
    if semua:
        teks = POLA_DAFTAR_SUMBER.sub("", teks).strip()
    teks, sumber = rapikan_sitasi(hapus_istilah_internal(bersihkan_format(teks)), semua, catatan["maks_sumber_luar"])
    return {"jawaban": teks, "sumber": sumber, "pakai_internet": any(s["url"] for s in semua)}


def bersihkan_format(teks):
    """Membuang tanda Markdown (bintang, pagar, backtick) dan catatan berpikir agar jawaban tampil sebagai teks biasa."""
    teks = re.sub(r"<think>.*?</think>", "", teks, flags=re.DOTALL)
    teks = re.sub(r"^\s{0,3}#{1,6}\s+", "", teks, flags=re.MULTILINE)
    teks = re.sub(r"^(\s*)[*+]\s+", r"\1- ", teks, flags=re.MULTILINE)
    teks = re.sub(r"\*\*|`", "", teks)
    teks = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", teks)
    teks = re.sub(r"\n{3,}", "\n\n", teks)
    return teks.strip()


def rapikan_sitasi(teks, semua, maks_sumber_luar):
    """Menyisakan sumber luar yang disitasi (jumlahnya dibatasi) dan menomori ulang [n] mulai dari 1.
    Data internal tidak pernah ditampilkan sebagai sumber, jadi nomornya dibuang."""
    dipakai = []

    def ganti(cocok):
        nomor = int(cocok.group(1))
        if not 1 <= nomor <= len(semua) or not semua[nomor - 1]["url"]:
            return ""
        if nomor not in dipakai:
            if len(dipakai) >= maks_sumber_luar:
                return ""
            dipakai.append(nomor)
        return f" [{dipakai.index(nomor) + 1}]"

    teks = POLA_SITASI.sub(ganti, teks).strip()
    # jawaban tanpa nomor sumber (selera, opini santai, logika) tidak menampilkan daftar sumber walaupun sempat mencari
    return teks, [semua[nomor - 1] for nomor in dipakai]