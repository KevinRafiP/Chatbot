def jawab(keadaan):
    """Simpul akhir normal: mengambil teks jawaban dari LLM."""
    bagian = keadaan["konten_terakhir"].get("parts", [])
    teks = "".join(b.get("text", "") for b in bagian if not b.get("thought")).strip()
    keadaan["hasil"] = hasil(keadaan, teks or "Maaf, saya belum bisa menjawab itu.")
    return keadaan


def batas(keadaan):
    """Simpul akhir saat putaran LLM sudah mencapai batas."""
    keadaan["hasil"] = hasil(keadaan, "Maaf, pencariannya terlalu panjang. Coba persempit pertanyaannya.")
    return keadaan


def hasil(keadaan, teks):
    sumber = keadaan["catatan"]["sumber"]
    return {"jawaban": teks, "sumber": sumber, "pakai_internet": bool(sumber)}