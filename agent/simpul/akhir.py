import re

POLA_SITASI = re.compile(r"\s*\[(\d+)\]")


def jawab(keadaan):
    """Simpul akhir normal: mengambil teks jawaban dari LLM lalu merapikannya."""
    bagian = keadaan["konten_terakhir"].get("content", [])
    teks = "".join(b.get("text", "") for b in bagian).strip()
    keadaan["hasil"] = hasil(keadaan, teks or "Maaf, saya belum bisa menjawab itu.")
    return keadaan


def batas(keadaan):
    """Simpul akhir saat putaran LLM sudah mencapai batas."""
    keadaan["hasil"] = hasil(keadaan, "Maaf, saya belum menemukan jawabannya dalam batas pencarian. Coba pertanyaan yang lebih spesifik.")
    return keadaan

def tolak(keadaan):
    """Simpul akhir untuk permintaan yang ditolak pengaman; LLM tidak dipanggil sama sekali."""
    keadaan["hasil"] = {
        "jawaban": "Maaf, saya tidak bisa membantu permintaan itu. Saya hanya bisa menjawab pertanyaan dan mencari informasi.",
        "sumber": [],
        "pakai_internet": False,
    }
    return keadaan

POLA_DAFTAR_SUMBER = re.compile(r"\n\s*(?:sumber(?: referensi)?|referensi|rujukan)\s*:.*\Z", re.IGNORECASE | re.DOTALL)

def hasil(keadaan, teks):
    catatan = keadaan["catatan"]
    semua = catatan["sumber"]
    if semua:
        teks = POLA_DAFTAR_SUMBER.sub("", teks).strip()
    teks, sumber = rapikan_sitasi(bersihkan_format(teks), semua, catatan["maks_sumber_luar"])
    return {"jawaban": teks, "sumber": sumber, "pakai_internet": any(s["url"] for s in semua)}


def bersihkan_format(teks):
    """Membuang tanda Markdown (bintang, pagar, backtick) dan catatan berpikir agar jawaban tampil sebagai teks biasa."""
    teks = re.sub(r"<think>.*?</think>", "", teks, flags=re.DOTALL)
    teks = re.sub(r"^\s{0,3}#{1,6}\s+", "", teks, flags=re.MULTILINE)
    teks = re.sub(r"^(\s*)[*+]\s+", r"\1- ", teks, flags=re.MULTILINE)
    teks = re.sub(r"\*\*|`", "", teks)
    teks = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", teks)
    teks = re.sub(r"\n{3,}", "\n\n", teks)
    return teks.strip()


def rapikan_sitasi(teks, semua, maks_sumber_luar):
    """Menyisakan sumber yang disitasi (sumber luar dibatasi jumlahnya) dan menomori ulang [n] mulai dari 1."""
    dipakai = []

    def ganti(cocok):
        nomor = int(cocok.group(1))
        if not 1 <= nomor <= len(semua):
            return ""
        if nomor not in dipakai:
            luar_terpakai = sum(1 for n in dipakai if semua[n - 1]["url"])
            if semua[nomor - 1]["url"] and luar_terpakai >= maks_sumber_luar:
                return ""
            dipakai.append(nomor)
        return f" [{dipakai.index(nomor) + 1}]"

    teks = POLA_SITASI.sub(ganti, teks).strip()
    if not dipakai:
        return teks, [s for s in semua if s["url"]][:maks_sumber_luar]
    return teks, [semua[nomor - 1] for nomor in dipakai]