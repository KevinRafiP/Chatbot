import logging

from llm.client import GalatLLM
from prompt import INSTRUKSI_SISTEM


def buat_pikir(klien):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada)."""

    def pikir(keadaan):
        try:
            konten = klien.kirim(INSTRUKSI_SISTEM, keadaan["isi"], keadaan["deklarasi"])
        except GalatLLM as galat:
            if galat.kode != 400 or not keadaan["deklarasi"] or keadaan["putaran_llm"] > 0:
                raise
            logging.warning("model menolak permintaan dengan alat, diulang tanpa alat: %s", galat)
            keadaan["deklarasi"] = None
            konten = klien.kirim(INSTRUKSI_SISTEM, keadaan["isi"], None)

        keadaan["isi"].append(konten)
        keadaan["konten_terakhir"] = konten
        keadaan["panggilan"] = [b["toolUse"] for b in konten.get("content", []) if "toolUse" in b]
        keadaan["putaran_llm"] += 1
        return keadaan

    return pikir