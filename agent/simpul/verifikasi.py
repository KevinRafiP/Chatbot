import logging
import re

POLA_SITASI = re.compile(r"\s*\[(?:data internal|sumber|source)?\s*(\d+)\]", re.IGNORECASE)
POLA_ANGKA = re.compile(r"\d+(?:[.,]\d+)*")
POLA_NAMA = re.compile(r"\b[A-Z][\w-]{2,}")
POLA_AWAL_BARIS = re.compile(r"^(\s*(?:-|\d+[.)])\s+)")
POLA_PISAH_KALIMAT = re.compile(r"(?<=[.!?])((?:\s*\[\d+\])*)\s+(?=\S)")
POLA_BARIS_TABEL = re.compile(r"^\s*\|")
POLA_RUMUS = re.compile(r"\$\$.+?\$\$|\\\[.+?\\\]|\\\(.+?\\\)|\$(?=\S)[^$\n]+?(?<=\S)\$")
# hitungan seperti "7,5 mg/kg × 15 kg = 112,5 mg": hasilnya dihitung model, jadi wajar tidak ada di sumber
POLA_OPERASI = re.compile(r"[×÷]|\d\s*[*/+^−]\s*[\w(\\]|\d\s*-\s*\(?\d")

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
    di_kode = di_rumus = False
    for baris in draf.split("\n"):
        # blok kode dan grafik (```) dibiarkan utuh, karena membuang sebagian barisnya membuat grafik rusak
        if baris.lstrip().startswith("```"):
            di_kode = not di_kode
            baris_baru.append(baris)
            continue
        if di_kode:
            baris_baru.append(baris)
            continue
        # rumus $$ beberapa baris dan baris tabel dibiarkan utuh, karena membuang satu barisnya membuat rumus atau tabel rusak
        ganti_rumus = baris.count("$$") % 2 == 1 or ("\\[" in baris) != ("\\]" in baris)
        if di_rumus or ganti_rumus:
            di_rumus = di_rumus != ganti_rumus
            baris_baru.append(baris)
            continue
        if POLA_BARIS_TABEL.match(baris):
            angka, nama = fakta(baris)
            baris_baru.append(periksa_sitasi(baris, angka | nama, isi_sumber))
            continue
        awal = POLA_AWAL_BARIS.match(baris)
        pembuka = awal.group(1) if awal else ""
        kalimat_baru = []
        for kalimat in pecah_kalimat(baris[len(pembuka):]):
            jumlah += 1
            angka, nama = fakta(kalimat)
            if not hitungan(kalimat) and any(not ada_di_rujukan(a, angka_rujukan) for a in angka):
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
    """Angka minimal dua digit, dan nama berhuruf kapital yang bukan kata pertama kalimat; isi rumus LaTeX tidak dihitung."""
    polos = POLA_RUMUS.sub(" ", POLA_SITASI.sub("", kalimat)).strip()
    angka = {a for a in POLA_ANGKA.findall(rapikan_angka(polos)) if len(a) >= 2}
    nama = {m.group(0).lower() for m in POLA_NAMA.finditer(polos) if m.start() > 0}
    return angka, nama

def hitungan(kalimat):
    """Kalimat berisi hitungan dengan tanda sama dengan, misalnya "Dosis = 7,5 mg/kg × 15 kg = 112,5 mg"."""
    polos = POLA_SITASI.sub("", kalimat)
    return "=" in polos and bool(POLA_OPERASI.search(polos))

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

def ada_di_rujukan(angka, angka_rujukan):
    """Angka dianggap ada jika sama persis, atau jika itu bentuk bulat dari angka sumber (16.250 dari 16250,1234)."""
    if angka in angka_rujukan:
        return True
    return len(angka) >= 3 and any(a.startswith(angka) and len(a) > len(angka) for a in angka_rujukan)

def rapikan_angka(teks):
    """1.000, 1,000, dan 1000 dianggap sama, begitu juga 08.00 dan 08:00."""
    return re.sub(r"(?<=\d)[.,:](?=\d)", "", teks)