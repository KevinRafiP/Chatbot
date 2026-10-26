import logging
import re
import time

from llm.client import GalatLLM
from prompt import INSTRUKSI_SISTEM

# galat sementara setelah alat dipakai tidak menggagalkan agen; jawaban disusun di simpul batas dari data yang terkumpul
KODE_SEMENTARA = {0, 204, 408, 429}
# setelah model menolak "wajib memakai alat", paksaan itu tidak dicoba lagi selama sekian detik,
# karena setiap penolakan membuang satu panggilan dan menunggu sampai batas diam
JEDA_COBA_WAJIB_DETIK = 3600
# jawaban model yang menyatakan informasinya tidak ada, padahal belum mencari ke internet
POLA_TIDAK_ADA_INFO = re.compile(
    r"\b(tidak|belum)\s+(memiliki|punya|menemukan|ada|tersedia|tercatat|disebutkan|diketahui)\b.{0,40}?\b(informasi|info|data|catatan|keterangan|sumber)"
    r"|\b(informasi|info|data|keterangan)\b.{0,60}?\b(tidak|belum)\s+(ada|tersedia|tercatat|ditemukan|disebutkan|diketahui)\b"
    r"|\btidak\s+tercatat\b|\bsaya\s+(tidak|belum)\s+tahu\b|\b(don'?t|do not)\s+have\s+(any\s+)?information\b")


def buat_pikir(klien, instruksi=INSTRUKSI_SISTEM):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada)."""
    
    ingat = {"tolak_wajib_sampai": 0.0}
    def pikir(keadaan):
        bisa_wajib = time.monotonic() >= ingat["tolak_wajib_sampai"]
        wajib = bool(keadaan.get("wajib_cari")) and keadaan["putaran_llm"] == 0 and bisa_wajib
        kabar = keadaan.get("kabar")
        sistem = instruksi + keadaan.get("instruksi_tambahan", "")
        tertulis = []

        def saat_teks(potongan):
            tertulis.append(potongan)
            # teks di putaran wajib cari biasanya hanya rencana model, jadi tetap di-stream (agar cepat) tapi tidak ditampilkan
            if not wajib:
                kabar("teks", {"teks": potongan})

        saat_teks = saat_teks if kabar else None
        try:
            konten = klien.kirim(sistem, keadaan["isi"], keadaan["deklarasi"], wajib, saat_teks)
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
                ingat["tolak_wajib_sampai"] = time.monotonic() + JEDA_COBA_WAJIB_DETIK
                keadaan["wajib_cari"] = False
                return pikir(keadaan)
            logging.warning("model gagal memakai alat, diulang tanpa alat: %s", galat)
            keadaan["deklarasi"] = None
            konten = klien.kirim(sistem, keadaan["isi"], None, False, saat_teks)
                
        if keadaan.pop("cari_cadangan", False) and bisa_wajib and keadaan["deklarasi"] and tidak_ada_info(konten):
            # data internal tidak menjawab dan model belum mencari, jadi jawabannya dibuang lalu diulang dengan wajib mencari
            logging.info("jawaban menyatakan informasi tidak ada, diulang dengan wajib mencari")
            if tertulis:
                kabar("ulang", {})
            keadaan["wajib_cari"] = True
            return pikir(keadaan)

        keadaan["isi"].append(konten)
        keadaan["konten_terakhir"] = konten
        keadaan["panggilan"] = [b["toolUse"] for b in konten.get("content", []) if "toolUse" in b]
        if tertulis and keadaan["panggilan"]:
            # teks tadi ternyata hanya pembuka sebelum memakai alat, jadi tampilan di browser dikosongkan lagi
            kabar("ulang", {})
        keadaan["putaran_llm"] += 1
        return keadaan

    return pikir

def tidak_ada_info(konten):
    """True jika model menjawab tanpa memakai alat dan jawabannya menyatakan informasinya tidak ada."""
    blok = konten.get("content", [])
    if any("toolUse" in b for b in blok):
        return False
    teks = " ".join(b.get("text", "") for b in blok).lower()
    return bool(POLA_TIDAK_ADA_INFO.search(teks))