import json
import logging
import re
import time

from llm.client import GalatLLM
from prompt import INSTRUKSI_OBROLAN, INSTRUKSI_SISTEM

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
# kata perintah dibuang dari kueri buatan agent agar mesin pencari hanya menerima topiknya
POLA_KATA_PERINTAH = re.compile(
    r"\b(tolong|coba|bisakah|bisa|sekarang|lalu|dan)?\s*(cari|carikan|cariin|telusuri|googling|search)(kan|in)?\s+(di|lewat|dari|ke)\s+(internet|web|google|online)\b"
    r"|\b(cari|carikan|cariin|telusuri|search)(kan|in)?\b"
    r"|\b(dengan|pakai|dari)?\s*(minimal|min|paling sedikit|setidaknya|sedikitnya|lebih dari)?\s*\d+\s+(sumber|referensi|rujukan|sources?)(\s+minimal)?\b"
    r"|\b(dan\s+)?(beri|berikan|sertakan|cantumkan|tampilkan|tulis|kasih)\w*\s+(juga\s+)?(sumber|referensi|rujukan|link)\w*"
    r"|\b(di|lewat|dari)\s+(internet|web|google)\b",
    re.IGNORECASE)
# kata yang tidak menandai topik, diabaikan saat mencocokkan kueri model dengan pertanyaan
KATA_UMUM = {"apa", "itu", "yang", "dan", "atau", "ada", "berapa", "siapa", "bagaimana", "kenapa", "mengapa", "dari", "dengan",
             "untuk", "dalam", "tentang", "ini", "saja", "the", "and", "what", "who", "how", "for"}
# sisa kueri yang lebih pendek dari ini berarti pertanyaan lanjutan ("cari lagi"), jadi pesan pengguna sebelumnya ikut dipakai
MIN_KATA_KUERI_SENDIRI = 2


def buat_pikir(klien, instruksi=INSTRUKSI_SISTEM, paksa_cari=False):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada).
    paksa_cari=True: jika wajib mencari tetapi model tidak memanggil cari_web, model diminta ulang lalu agent mencari sendiri."""
    
    ingat = {"tolak_wajib_sampai": 0.0}
    def pikir(keadaan):
        bisa_wajib = time.monotonic() >= ingat["tolak_wajib_sampai"]
        wajib = bool(keadaan.get("wajib_cari")) and keadaan["putaran_llm"] == 0 and bisa_wajib
        kabar = keadaan.get("kabar")
        sistem = INSTRUKSI_OBROLAN if keadaan.get("obrolan") else instruksi + keadaan.get("instruksi_tambahan", "")
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

        if wajib and paksa_cari and ada_alat(keadaan, "cari_web"):
            if not ada_panggilan(konten):
                konten = paksa_panggil_cari(klien, sistem, keadaan)
            luruskan_kueri(konten, keadaan)

        keadaan["isi"].append(konten)
        keadaan["konten_terakhir"] = konten
        keadaan["panggilan"] = [b["toolUse"] for b in konten.get("content", []) if "toolUse" in b]
        if tertulis and keadaan["panggilan"]:
            # teks tadi ternyata hanya pembuka sebelum memakai alat, jadi tampilan di browser dikosongkan lagi
            kabar("ulang", {})
        keadaan["putaran_llm"] += 1
        return keadaan

    return pikir

def ada_panggilan(konten):
    return any("toolUse" in b for b in konten.get("content", []))

def ada_alat(keadaan, nama):
    return any(d.get("name") == nama for d in keadaan.get("deklarasi") or [])

def pesan_wajib(keadaan):
    """Model lokal (Ollama) mengabaikan pilihan "wajib memakai alat", jadi model diminta ulang dengan pesan tegas.
    Daftar alat diambil dari deklarasi pertanyaan ini, jadi alat baru otomatis ikut tercantum."""
    nama = ", ".join(d["name"] for d in keadaan.get("deklarasi") or [])
    return ("Jangan menjawab dulu. Panggil sekarang alat yang paling cocok untuk pertanyaan terakhir pengguna, "
            f"pilih dari: {nama}. Pakai alat khusus jika deskripsinya cocok; "
            "cari_web hanya untuk fakta yang tidak bisa dijawab alat lain.")

def paksa_panggil_cari(klien, sistem, keadaan):
    """Meminta model sekali lagi memanggil cari_web; jika tetap tidak, agent membuat panggilan cari_web sendiri dari pertanyaan."""
    logging.info("model tidak memanggil alat walau wajib mencari, diminta ulang")
    isi = keadaan["isi"] + [{"role": "user", "content": [{"text": pesan_wajib(keadaan)}]}]
    try:
        konten = klien.kirim(sistem, isi, keadaan["deklarasi"], True)
        if ada_panggilan(konten):
            return konten
    except GalatLLM as galat:
        logging.warning("permintaan ulang cari_web gagal: %s", galat)

    kueri = kueri_sendiri(keadaan)
    logging.info("agent mencari sendiri: %s", kueri)
    nomor = f"cari_sendiri_{keadaan['putaran_llm']}"
    argumen = {"kueri": kueri}
    # "asli" adalah bentuk format OpenAI yang dikirim balik ke layanan saat percakapan dilanjutkan
    asli = {"id": nomor, "type": "function",
            "function": {"name": "cari_web", "arguments": json.dumps(argumen, ensure_ascii=False)}}
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": nomor, "name": "cari_web", "input": argumen, "asli": asli}}]}

def kueri_sendiri(keadaan):
    """Pertanyaan terakhir tanpa kata perintah sebagai kueri; jika sisanya terlalu pendek, pesan pengguna sebelumnya ikut dipakai."""
    asli = " ".join(str(keadaan.get("pertanyaan", "")).split())
    kueri = bersihkan_kueri(asli)
    if len(kueri.split()) < MIN_KATA_KUERI_SENDIRI:
        sebelumnya = [str(p.get("teks", "")) for p in (keadaan.get("riwayat") or []) if p.get("peran") != "asisten"]
        if sebelumnya:
            kueri = f"{bersihkan_kueri(sebelumnya[-1])} {kueri}".strip()
    return (kueri or asli)[:300]

def luruskan_kueri(konten, keadaan):
    """Kueri cari_web dari model yang tidak memuat satu pun kata topik pertanyaan diganti kueri buatan agent,
    karena model kecil kadang mencari topik dari ingatan atau Data internal, bukan dari pertanyaan."""
    pengganti = kueri_sendiri(keadaan)
    topik = kata_topik(pengganti)
    for blok in konten.get("content", []):
        panggilan = blok.get("toolUse")
        if not panggilan or panggilan.get("name") != "cari_web":
            continue
        kueri = str((panggilan.get("input") or {}).get("kueri", ""))
        if topik and not topik & kata_topik(kueri):
            logging.info("kueri model tidak sesuai pertanyaan (%s), diganti: %s", kueri, pengganti)
            panggilan["input"] = {**(panggilan.get("input") or {}), "kueri": pengganti}
            fungsi = (panggilan.get("asli") or {}).get("function")
            if isinstance(fungsi, dict):
                fungsi["arguments"] = json.dumps(panggilan["input"], ensure_ascii=False)

def kata_topik(teks):
    return {kata for kata in re.findall(r"\w+", teks.lower()) if len(kata) >= 3 and kata not in KATA_UMUM}

def bersihkan_kueri(teks):
    return " ".join(POLA_KATA_PERINTAH.sub(" ", teks).split()).strip(" ,.?!")

def tidak_ada_info(konten):
    """True jika model menjawab tanpa memakai alat dan jawabannya menyatakan informasinya tidak ada."""
    blok = konten.get("content", [])
    if any("toolUse" in b for b in blok):
        return False
    teks = " ".join(b.get("text", "") for b in blok).lower()
    return bool(POLA_TIDAK_ADA_INFO.search(teks))