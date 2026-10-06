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
    keadaan["hasil"] = hasil(keadaan, "Maaf, pencariannya terlalu panjang. Coba persempit pertanyaannya.")
    return keadaan


def hasil(keadaan, teks):
    semua = keadaan["catatan"]["sumber"]
    teks, sumber = rapikan_sitasi(bersihkan_format(teks), semua)
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


def rapikan_sitasi(teks, semua):
    """Menyisakan sumber yang benar-benar disitasi dan menomori ulang [n] mulai dari 1."""
    dipakai = []

    def ganti(cocok):
        nomor = int(cocok.group(1))
        if not 1 <= nomor <= len(semua):
            return ""
        if nomor not in dipakai:
            dipakai.append(nomor)
        return f" [{dipakai.index(nomor) + 1}]"

    teks = POLA_SITASI.sub(ganti, teks).strip()
    if not dipakai:
        return teks, [s for s in semua if s["url"]]
    return teks, [semua[nomor - 1] for nomor in dipakai]