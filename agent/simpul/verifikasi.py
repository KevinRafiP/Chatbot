import logging
import re

POLA_SITASI = re.compile(r"\s*\[(\d+)\]")
POLA_ANGKA = re.compile(r"\d+(?:[.,]\d+)*")
POLA_NAMA = re.compile(r"\b[A-Z][\w-]{2,}")
POLA_AWAL_BARIS = re.compile(r"^(\s*(?:-|\d+[.)])\s+)")
POLA_PISAH_KALIMAT = re.compile(r"(?<=[.!?])((?:\s*\[\d+\])*)\s+(?=\S)")

# jika lebih dari separuh kalimat harus dibuang, jawaban dipakai utuh dengan catatan agar tidak tersisa potongan
RASIO_BUANG_MAKSIMAL = 0.5
CATATAN_RAGU = "Catatan: sebagian angka di jawaban ini tidak ditemukan di sumber, jadi mohon dicek ulang."


def verifikasi(keadaan):
    """Memeriksa draf terhadap semua yang dibaca model, tanpa LLM:
    kalimat berisi angka yang tidak ada di sumber dibuang, sitasi [n] yang tidak memuat angka atau nama di kalimatnya dipindah atau dibuang."""
    catatan = keadaan["catatan"]
    if not any(sumber["url"] for sumber in catatan["sumber"]):
        return keadaan

    draf = "".join(b.get("text", "") for b in keadaan["konten_terakhir"].get("content", [])).strip()
    if not draf:
        return keadaan

    rujukan = rapikan_angka(teks_terbaca(keadaan).lower())
    angka_rujukan = set(POLA_ANGKA.findall(rujukan))
    isi_sumber = {
        nomor: rapikan_angka(f"{catatan['sumber'][nomor - 1]['judul']}\n{bukti.get('isi', '')}".lower())
        for nomor, bukti in catatan["bukti"].items() if 1 <= nomor <= len(catatan["sumber"])
    }

    baris_baru, jumlah, dibuang = [], 0, []
    for baris in draf.split("\n"):
        awal = POLA_AWAL_BARIS.match(baris)
        pembuka = awal.group(1) if awal else ""
        kalimat_baru = []
        for kalimat in pecah_kalimat(baris[len(pembuka):]):
            jumlah += 1
            angka, nama = fakta(kalimat)
            if angka - angka_rujukan:
                dibuang.append(kalimat)
                continue
            kalimat_baru.append(periksa_sitasi(kalimat, angka | nama, isi_sumber))
        if kalimat_baru or not baris.strip():
            baris_baru.append(pembuka + " ".join(kalimat_baru))

    if dibuang:
        logging.info("verifikasi membuang %d dari %d kalimat: %s", len(dibuang), jumlah, dibuang)
    if len(dibuang) > jumlah * RASIO_BUANG_MAKSIMAL:
        teks = f"{draf}\n\n{CATATAN_RAGU}"
    else:
        teks = re.sub(r"\n{3,}", "\n\n", "\n".join(baris_baru)).strip() or draf
    keadaan["konten_terakhir"] = {"role": "assistant", "content": [{"text": teks}]}
    return keadaan


def teks_terbaca(keadaan):
    """Semua teks yang dikirim ke model (riwayat, data internal, tanggal, hasil alat), tanpa draf dan tanpa teks putaran alat."""
    potongan = []
    for pesan in keadaan["isi"]:
        if pesan is keadaan["konten_terakhir"]:
            continue
        blok = pesan.get("content", [])
        if pesan.get("role") == "assistant" and any("toolUse" in b for b in blok):
            continue
        for b in blok:
            potongan.append(b.get("text", ""))
            for hasil in b.get("toolResult", {}).get("content", []):
                potongan.append(hasil.get("text", ""))
    return "\n".join(potongan)


def pecah_kalimat(teks):
    """Memecah satu baris menjadi kalimat; sitasi di belakang titik ikut kalimat sebelumnya."""
    potongan = POLA_PISAH_KALIMAT.split(teks.strip())
    hasil = []
    for i in range(0, len(potongan), 2):
        kalimat = (potongan[i] + (potongan[i + 1] if i + 1 < len(potongan) else "")).strip()
        if kalimat:
            hasil.append(kalimat)
    return hasil


def fakta(kalimat):
    """Angka minimal dua digit, dan nama berhuruf kapital yang bukan kata pertama kalimat."""
    polos = POLA_SITASI.sub("", kalimat).strip()
    angka = {a for a in POLA_ANGKA.findall(rapikan_angka(polos)) if len(a) >= 2}
    nama = {m.group(0).lower() for m in POLA_NAMA.finditer(polos) if m.start() > 0}
    return angka, nama


def periksa_sitasi(kalimat, kunci, isi_sumber):
    """Sitasi [n] yang sumbernya tidak memuat satu pun angka atau nama di kalimat dipindah ke sumber yang memuatnya, atau dibuang."""
    if not kunci:
        return kalimat

    def cocok(nomor):
        isi = isi_sumber.get(nomor, "")
        return sum(1 for k in kunci if k in isi)

    def ganti(sitasi):
        nomor = int(sitasi.group(1))
        if nomor not in isi_sumber or cocok(nomor):
            return sitasi.group(0)
        terbaik = max(isi_sumber, key=cocok)
        return f" [{terbaik}]" if cocok(terbaik) else ""

    return POLA_SITASI.sub(ganti, kalimat).strip()


def rapikan_angka(teks):
    """1.000, 1,000, dan 1000 dianggap sama, begitu juga 08.00 dan 08:00."""
    return re.sub(r"(?<=\d)[.,:](?=\d)", "", teks)