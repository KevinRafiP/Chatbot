from prompt import INSTRUKSI_SISTEM


def buat_pikir(klien):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada)."""

    def pikir(keadaan):
        konten = klien.kirim(INSTRUKSI_SISTEM, keadaan["isi"], keadaan["deklarasi"])
        keadaan["isi"].append(konten)
        keadaan["konten_terakhir"] = konten
        keadaan["panggilan"] = [b["functionCall"] for b in konten.get("parts", []) if "functionCall" in b]
        keadaan["putaran_llm"] += 1
        return keadaan

    return pikir