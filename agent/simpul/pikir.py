import logging

from llm.client import GalatLLM
from prompt import INSTRUKSI_SISTEM

# galat sementara setelah alat dipakai tidak menggagalkan agen; jawaban disusun di simpul batas dari data yang terkumpul
KODE_SEMENTARA = {0, 204, 408, 429}


def buat_pikir(klien, instruksi=INSTRUKSI_SISTEM):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada)."""

    def pikir(keadaan):
        wajib = bool(keadaan.get("wajib_cari")) and keadaan["putaran_llm"] == 0
        kabar = keadaan.get("kabar")
        tertulis = []

        def saat_teks(potongan):
            tertulis.append(potongan)
            # teks di putaran wajib cari biasanya hanya rencana model, jadi tetap di-stream (agar cepat) tapi tidak ditampilkan
            if not wajib:
                kabar("teks", {"teks": potongan})

        saat_teks = saat_teks if kabar else None
        try:
            konten = klien.kirim(instruksi, keadaan["isi"], keadaan["deklarasi"], wajib, saat_teks)
        except GalatLLM as galat:
            if keadaan["putaran_llm"] > 0 and (galat.kode in KODE_SEMENTARA or galat.kode >= 500):
                logging.warning("model gagal setelah memakai alat, jawaban disusun dari data yang terkumpul: %s", galat)
                if tertulis:
                    kabar("ulang", {})
                keadaan["ke_batas"] = True
                return keadaan
            # 400 = model menolak alat, 204 = model diam saat diberi alat (sering terjadi di model lokal kecil)
            if galat.kode not in (400, 204) or not keadaan["deklarasi"] or keadaan["putaran_llm"] > 0:
                raise
            if wajib:
                # sebagian model tidak mendukung pilihan "wajib memakai alat", jadi diulang dengan alat biasa
                logging.warning("model menolak wajib memakai alat, diulang tanpa paksaan: %s", galat)
                keadaan["wajib_cari"] = False
                return pikir(keadaan)
            logging.warning("model gagal memakai alat, diulang tanpa alat: %s", galat)
            keadaan["deklarasi"] = None
            konten = klien.kirim(instruksi, keadaan["isi"], None, False, saat_teks)

        keadaan["isi"].append(konten)
        keadaan["konten_terakhir"] = konten
        keadaan["panggilan"] = [b["toolUse"] for b in konten.get("content", []) if "toolUse" in b]
        if tertulis and keadaan["panggilan"]:
            # teks tadi ternyata hanya pembuka sebelum memakai alat, jadi tampilan di browser dikosongkan lagi
            kabar("ulang", {})
        keadaan["putaran_llm"] += 1
        return keadaan

    return pikir