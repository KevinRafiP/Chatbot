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
# model yang hanya diam (kode 204) bisa sekadar lambat sesaat, jadi paksaan baru dijeda jika diam sekian kali berturut-turut
BATAS_DIAM_WAJIB = 2
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
# alat hitung: jika model sudah memanggil salah satunya, agent tidak menambahkan cari_web (hitungan tidak perlu dicari di internet)
ALAT_HITUNG = {"hitung", "keuangan", "konversi", "kalkulus", "waktu_tanggal", "acak", "jalankan_python"}
PESAN_ALAT_PASTI = ("Jangan menjawab dulu. Hasil pertanyaan ini harus dihitung dengan alat, bukan dikira-kira. "
                    "Panggil sekarang alat yang cocok: {alat}.")
PESAN_WAJIB_DATA = ("Jangan menjawab dulu. Ada data yang dibutuhkan hitungan ini tetapi tidak diberikan pengguna (misalnya spesifikasi, "
                    "daya, harga, atau tarif). Panggil cari_web sekarang untuk mencarinya; hitung setelah datanya ada.")


def buat_pikir(klien, instruksi=INSTRUKSI_SISTEM, paksa_cari=False):
    """Simpul yang mengirim percakapan ke LLM dan mencatat permintaan alat (jika ada).
    paksa_cari=True: jika wajib mencari tetapi model tidak memanggil cari_web, model diminta ulang lalu agent mencari sendiri."""
    
    ingat = {"tolak_wajib_sampai": 0.0, "diam_berturut": 0}
    def pikir(keadaan):
        bisa_wajib = time.monotonic() >= ingat["tolak_wajib_sampai"]
        wajib = bool(keadaan.get("wajib_cari")) and keadaan["putaran_llm"] == 0 and bisa_wajib
        kabar = keadaan.get("kabar")
        sistem = (INSTRUKSI_OBROLAN if keadaan.get("obrolan") else instruksi) + keadaan.get("instruksi_tambahan", "")
        tertulis = []

        def saat_teks(potongan):
            tertulis.append(potongan)
            # teks di putaran wajib cari biasanya hanya rencana model, jadi tetap di-stream (agar cepat) tapi tidak ditampilkan
            if not wajib:
                kabar("teks", {"teks": potongan})

        saat_teks = saat_teks if kabar else None
        isi, saat_kirim = keadaan["isi"], saat_teks
        paksa_awal = wajib and paksa_cari and bool(keadaan["deklarasi"])
        if paksa_awal:
            # Ollama mengabaikan "wajib memakai alat", jadi pesan tegas langsung ikut dikirim agar model tidak menulis jawaban dari ingatan dulu;
            # tanpa stream seperti permintaan ulang, karena panggilan alat lewat stream Ollama kadang terbaca kosong
            isi = isi + [{"role": "user", "content": [{"text": PESAN_WAJIB_DATA if keadaan.get("butuh_data") else pesan_wajib(keadaan)}]}]
            saat_kirim = None
        try:
            konten = klien.kirim(sistem, isi, keadaan["deklarasi"], wajib, saat_kirim)
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
            if paksa_awal and ada_alat(keadaan, "cari_web"):
                # pesan tegas sudah dikirim; mengulang tanpa paksaan hanya membuat model menulis jawaban dari ingatan, jadi agent mencari sendiri
                logging.warning("model gagal memanggil alat di putaran wajib, agent mencari sendiri: %s", galat)
                konten = cari_sendiri(keadaan, keadaan.get("kueri_rencana") or kueri_sendiri(keadaan), "cari_sendiri")
            elif wajib:
                # sebagian model tidak mendukung pilihan "wajib memakai alat" (400), jadi diulang dengan alat biasa
                logging.warning("model menolak wajib memakai alat, diulang tanpa paksaan: %s", galat)
                ingat["diam_berturut"] = ingat["diam_berturut"] + 1 if galat.kode == 204 else BATAS_DIAM_WAJIB
                if ingat["diam_berturut"] >= BATAS_DIAM_WAJIB:
                    ingat["tolak_wajib_sampai"] = time.monotonic() + JEDA_COBA_WAJIB_DETIK
                    ingat["diam_berturut"] = 0
                keadaan["wajib_cari"] = False
                return pikir(keadaan)
            else:
                logging.warning("model gagal memakai alat, diulang tanpa alat: %s", galat)
                keadaan["deklarasi"] = None
                konten = klien.kirim(sistem, keadaan["isi"], None, False, saat_teks)
        if wajib:
            ingat["diam_berturut"] = 0
                
        if keadaan.pop("cari_cadangan", False) and bisa_wajib and keadaan["deklarasi"] and tidak_ada_info(konten):
            # data internal tidak menjawab dan model belum mencari, jadi jawabannya dibuang lalu diulang dengan wajib mencari
            logging.info("jawaban menyatakan informasi tidak ada, diulang dengan wajib mencari")
            if tertulis:
                kabar("ulang", {})
            keadaan["wajib_cari"] = True
            return pikir(keadaan)

        pasti = keadaan.get("alat_pasti") if keadaan["putaran_llm"] == 0 else None
        if pasti and not ada_panggilan(konten):
            konten = minta_alat_pasti(klien, sistem, keadaan, pasti) or konten

        # pencarian yang wajib tetapi tidak bisa dipaksakan ke model (paksaan dijeda atau model diam) tetap dijalankan:
        # jika model langsung menjawab tanpa alat, jawaban dari ingatan itu diganti pencarian oleh agent
        tertunda = keadaan["putaran_llm"] == 0 and not wajib and keadaan.get("wajib_web")
        if tertunda and ada_alat(keadaan, "cari_web") and not ada_panggilan(konten):
            konten = cari_sendiri(keadaan, keadaan.get("kueri_rencana") or kueri_sendiri(keadaan), "cari_tertunda")
            logging.info("model menjawab tanpa mencari padahal wajib, agent mencari sendiri: %s", konten["content"][0]["toolUse"]["input"]["kueri"])

        if wajib and paksa_cari and ada_alat(keadaan, "cari_web"):
            # data yang belum diberikan pengguna (misalnya daya GPU atau tarif listrik) dicari dulu, bukan diasumsikan
            harus_web = bool(keadaan.get("butuh_data")) and not memanggil(konten, "cari_web")
            if not ada_panggilan(konten) or harus_web:
                konten = paksa_panggil_cari(klien, sistem, keadaan, harus_web)
            luruskan_kueri(konten, keadaan)
        if (wajib and ada_alat(keadaan, "cari_web") and ada_panggilan(konten) and not memanggil(konten, "cari_web")
                and not any(memanggil(konten, nama) for nama in ALAT_HITUNG)):
            tambah_cari_web(konten, keadaan)

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

def memanggil(konten, nama):
    return any(b["toolUse"].get("name") == nama for b in konten.get("content", []) if "toolUse" in b)

def ada_alat(keadaan, nama):
    return any(d.get("name") == nama for d in keadaan.get("deklarasi") or [])

def pesan_wajib(keadaan):
    """Model lokal (Ollama) mengabaikan pilihan "wajib memakai alat", jadi model diminta ulang dengan pesan tegas.
    Daftar alat diambil dari deklarasi pertanyaan ini, jadi alat baru otomatis ikut tercantum."""
    nama = ", ".join(d["name"] for d in keadaan.get("deklarasi") or [])
    return ("Jangan menjawab dulu. Panggil sekarang alat yang paling cocok untuk pertanyaan terakhir pengguna, "
            f"pilih dari: {nama}. Pakai alat khusus jika deskripsinya cocok; "
            "cari_web hanya untuk fakta yang tidak bisa dijawab alat lain.")

def minta_alat_pasti(klien, sistem, keadaan, alat):
    """Model menjawab tanpa alat padahal hasilnya harus dihitung alat (tanggal, kurs, cicilan, acak): model diminta sekali lagi tanpa
    paksaan Bedrock (yang bisa macet). Mengembalikan balasan baru jika memanggil alat, None jika tetap tidak."""
    isi = keadaan["isi"] + [{"role": "user", "content": [{"text": PESAN_ALAT_PASTI.format(alat=", ".join(alat))}]}]
    try:
        konten = klien.kirim(sistem, isi, keadaan["deklarasi"], False)
    except GalatLLM as galat:
        logging.warning("permintaan ulang alat %s gagal: %s", ", ".join(alat), galat)
        return None
    if not ada_panggilan(konten):
        logging.info("model tetap tidak memanggil alat %s", ", ".join(alat))
        return None
    logging.info("model menjawab tanpa alat %s, diminta ulang dan sekarang memanggil alat", ", ".join(alat))
    return konten

def paksa_panggil_cari(klien, sistem, keadaan, harus_web=False):
    """Meminta model sekali lagi memanggil alat (cari_web jika harus_web); jika tetap tidak, agent membuat panggilan cari_web sendiri."""
    pesan = PESAN_WAJIB_DATA if harus_web else pesan_wajib(keadaan)
    isi = keadaan["isi"] + [{"role": "user", "content": [{"text": pesan}]}]
    try:
        konten = klien.kirim(sistem, isi, keadaan["deklarasi"], True)
        if ada_panggilan(konten) and (not harus_web or memanggil(konten, "cari_web")):
            return konten
    except GalatLLM as galat:
        logging.warning("permintaan ulang cari_web gagal: %s", galat)

    kueri = kueri_sendiri(keadaan)
    logging.info("agent mencari sendiri: %s", kueri)
    return cari_sendiri(keadaan, kueri, "cari_sendiri")

def cari_sendiri(keadaan, kueri, awalan):
    """Giliran model buatan agent yang hanya berisi satu panggilan cari_web; format OpenAI-nya dibuat di llm.api saat dikirim."""
    nomor = f"{awalan}_{keadaan['putaran_llm']}"
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": nomor, "name": "cari_web", "input": {"kueri": kueri}}}]}

def tambah_cari_web(konten, keadaan):
    """Pilihan "wajib memakai alat" Bedrock sudah terpenuhi oleh alat apa pun, misalnya cari_gambar, sehingga fakta tetap ditulis dari
    ingatan. Jika pemahaman punya kata kunci fakta, agent menambahkan satu cari_web sendiri tanpa memanggil model lagi."""
    kueri = keadaan.get("kueri_rencana") or (kueri_sendiri(keadaan) if (keadaan.get("catatan") or {}).get("dugaan") else "")
    if not kueri:
        return
    nomor = f"cari_tambahan_{keadaan['putaran_llm']}"
    argumen = {"kueri": kueri}
    panggilan = {"toolUseId": nomor, "name": "cari_web", "input": argumen}
    # "asli" hanya untuk format OpenAI (model lokal); Bedrock menolak kunci yang tidak dikenalnya
    if any("asli" in b["toolUse"] for b in konten.get("content", []) if "toolUse" in b):
        panggilan["asli"] = {"id": nomor, "type": "function",
                             "function": {"name": "cari_web", "arguments": json.dumps(argumen, ensure_ascii=False)}}
    konten.setdefault("content", []).append({"toolUse": panggilan})
    logging.info("model tidak memanggil cari_web di putaran wajib, agent menambahkan: %s", kueri)

def kueri_sendiri(keadaan):
    """Pertanyaan terakhir tanpa kata perintah sebagai kueri; jika sisanya terlalu pendek, pesan pengguna sebelumnya ikut dipakai."""
    asli = " ".join(str(keadaan.get("pertanyaan_lengkap") or keadaan.get("pertanyaan", "")).split())
    kueri = bersihkan_kueri(asli)
    if keadaan.get("rujukan"):
        return f"{bersihkan_kueri(keadaan['rujukan'])} {kueri}".strip()[:300]
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
    rujukan = bersihkan_kueri(keadaan.get("rujukan", ""))
    # nama yang muncul dari tulis ulang ("Eiichiro Oda" untuk "umurnya berapa?") wajib ada di kueri model
    nama = kata_nama(keadaan.get("pertanyaan_lengkap", "")) - kata_topik(str(keadaan.get("pertanyaan", "")))
    for blok in konten.get("content", []):
        panggilan = blok.get("toolUse")
        if not panggilan or panggilan.get("name") != "cari_web":
            continue
        kueri = str((panggilan.get("input") or {}).get("kueri", ""))
        if rujukan:
            # pesan lanjutan: kueri model tetap dipakai (bisa sudah memuat nama dari jawaban sebelumnya),
            # hanya ditambah topik pertanyaan sebelumnya jika belum ada
            # kueri dibiarkan jika memuat topik sebelumnya atau nama dari riwayat yang tidak ada di pesan ini (misalnya nama dari jawaban sebelumnya)
            baru_dari_model = kata_topik(kueri) - kata_topik(str(keadaan.get("pertanyaan", "")))
            if kata_topik(rujukan) & kata_topik(kueri) or baru_dari_model & kata_riwayat(keadaan.get("riwayat")):
                continue
            baru = f"{rujukan} {kueri}"[:300]
        elif nama and not nama & kata_topik(kueri):
            baru = pengganti
        elif topik and not topik & kata_topik(kueri):
            baru = pengganti
        else:
            continue
        logging.info("kueri model tidak sesuai pertanyaan (%s), diganti: %s", kueri, baru)
        panggilan["input"] = {**(panggilan.get("input") or {}), "kueri": baru}
        fungsi = (panggilan.get("asli") or {}).get("function")
        if isinstance(fungsi, dict):
            fungsi["arguments"] = json.dumps(panggilan["input"], ensure_ascii=False)

def kata_nama(teks):
    """Kata topik berhuruf awal kapital, selain kata pertama kalimat."""
    return kata_topik(" ".join(re.findall(r"(?<=\s)[A-Z]\w*", str(teks or ""))))

def kata_riwayat(riwayat):
    return kata_topik(" ".join(str(p.get("teks", "")) for p in (riwayat or []) if isinstance(p, dict)))

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