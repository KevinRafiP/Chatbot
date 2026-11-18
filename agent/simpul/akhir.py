import logging
import re

from alat.gambar_web import (BATAS_TUNGGU_GAMBAR, BATAS_TUNGGU_SUSULAN, POLA_PENANDA_GAMBAR, ciri_subjek, gambar_susulan, kata_kunci,
                             tunggu_gambar)
from llm.client import GalatLLM
from simpul.siapkan import TANDA_DIPERSINGKAT

POLA_PEMISAH_TABEL = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
POLA_SITASI = re.compile(r"\s*\[(?:data internal|sumber|source)?\s*(\d+)\]", re.IGNORECASE)


def jawab(keadaan):
    """Simpul akhir normal: mengambil teks jawaban dari LLM lalu merapikannya."""
    bagian = keadaan["konten_terakhir"].get("content", [])
    teks = "".join(b.get("text", "") for b in bagian).strip()
    keadaan["hasil"] = hasil(keadaan, teks or "Maaf, saya belum bisa menjawab itu.")
    return keadaan

JAWABAN_BATAS = "Maaf, saya belum menemukan jawabannya dalam batas pencarian. Coba pertanyaan yang lebih spesifik."
PESAN_JAWAB_SEKARANG = (
    "Batas pencarian sudah tercapai dan alat tidak bisa dipakai lagi. Jawab pertanyaan terakhir pengguna sekarang "
    "hanya dari informasi di atas. Jika belum cukup, sebut singkat bagian yang tidak ditemukan, lalu beri penjelasan umum."
)


def buat_batas(klien, instruksi):
    """Simpul saat putaran LLM habis: model diminta menjawab sekali lagi tanpa alat dari semua yang sudah terkumpul."""

    def batas(keadaan):
        kabar = keadaan.get("kabar")
        if kabar:
            kabar("status", {"teks": "Menyusun jawaban"})
        bahan = f"{gabung_percakapan(keadaan['isi'])}\n\n{PESAN_JAWAB_SEKARANG}"
        saat_teks = (lambda potongan: kabar("teks", {"teks": potongan})) if kabar else None
        try:
            konten = klien.kirim(instruksi + keadaan.get("instruksi_tambahan", ""), [{"role": "user", "content": [{"text": bahan}]}], None, False, saat_teks)
        except GalatLLM as galat:
            logging.warning("jawaban di batas pencarian gagal: %s", galat)
            konten = {}
        if not "".join(b.get("text", "") for b in konten.get("content", [])).strip():
            konten = {"role": "assistant", "content": [{"text": JAWABAN_BATAS}]}
        keadaan["konten_terakhir"] = konten
        return keadaan

    return batas

def gabung_percakapan(isi):
    """Percakapan berisi alat dijadikan satu teks biasa, karena Bedrock menolak blok alat tanpa daftar alat."""
    potongan = []
    for pesan in isi:
        blok = pesan.get("content", [])
        if pesan.get("role") == "assistant":
            if not any("toolUse" in b for b in blok):
                potongan += [f"Asisten: {b['text']}" for b in blok if b.get("text")]
            continue
        for b in blok:
            if b.get("text"):
                potongan.append(b["text"])
            for hasil_alat in b.get("toolResult", {}).get("content", []):
                potongan.append(f"Hasil alat: {hasil_alat.get('text', '')}")
    return "\n\n".join(potongan)

def tolak(keadaan):
    """Simpul akhir untuk permintaan yang ditolak pengaman; LLM tidak dipanggil sama sekali."""
    keadaan["hasil"] = {
        "jawaban": "Maaf, saya tidak bisa membantu permintaan itu. Saya hanya bisa menjawab pertanyaan dan mencari informasi.",
        "sumber": [],
        "pakai_internet": False,
    }
    return keadaan

# daftar sumber buatan model di akhir jawaban, juga yang ditulis tebal, sebagai judul, atau diawali garis pemisah
POLA_DAFTAR_SUMBER = re.compile(r"\n\s*(?:[-*_]{3,}\s*\n\s*)?(?:#{1,6}\s*)?[*_]{0,2}(?:sumber(?: referensi)?|referensi|rujukan)\s*(?::[*_]{0,2}|[*_]{0,2}:).*\Z",
                                re.IGNORECASE | re.DOTALL)

ISTILAH = r"(?:data internal|catatan saya|ingatan saya|(?:hasil )?(?:pemahaman|memahami) pertanyaan(?: ini)?)(?:\s+(?:yang\s+)?(?:tersedia|ada|saya miliki|saya punya|kami))?"
# "Dari data internal yang tersedia, Kevin ..." di awal kalimat
POLA_PEMBUKA_INTERNAL = re.compile(rf"(^|(?<=[.!?]\s)|(?<=\n))(?:dari|berdasarkan|menurut|sesuai(?: dengan)?|di|dalam)\s+{ISTILAH}\s*,\s*(\w)", re.IGNORECASE | re.MULTILINE)
# "... tentang X dalam data internal yang tersedia." di akhir kalimat atau anak kalimat
POLA_KETERANGAN_INTERNAL = re.compile(rf"\s+(?:dari|berdasarkan|menurut|di|dalam)\s+{ISTILAH}(?=[.,!?;:\n]|$)", re.IGNORECASE)

# kalimat pembuka yang menceritakan catatan sistem atau permintaan pengguna, misalnya "Berdasarkan riwayat percakapan, pengguna meminta ..."
POLA_KALIMAT_META = re.compile(r"\b(?:riwayat percakapan|catatan sistem|rencana jawaban|(?:pemahaman|memahami) pertanyaan)\b"
                               r"|^\W*(?:pengguna|user)\s+(?:meminta|menanyakan|ingin|bertanya|mencari|menginginkan)\b", re.IGNORECASE)


def buang_kalimat_meta(teks):
    """Kalimat seperti itu di paragraf pertama dibuang; kalimat lain di paragraf itu tetap."""
    bagian = teks.split("\n\n", 1)
    if bagian[0].lstrip().startswith(("#", "|", "```")):
        return teks
    kalimat = re.split(r"(?<=[.!?])\s+", bagian[0].strip())
    sisa = " ".join(k for k in kalimat if not POLA_KALIMAT_META.search(k))
    if len(sisa) == len(" ".join(kalimat)):
        return teks
    return "\n\n".join(([sisa] if sisa else []) + bagian[1:])


def hapus_istilah_internal(teks):
    """Membuang frasa yang menyebut data internal atau catatan, karena asal jawaban tidak boleh ditampilkan."""
    teks = buang_kalimat_meta(teks)
    teks = POLA_PEMBUKA_INTERNAL.sub(lambda c: c.group(1) + c.group(2).upper(), teks)
    teks = POLA_KETERANGAN_INTERNAL.sub("", teks)
    return re.sub(r"\b(d)ata internal\b", lambda c: f"{c.group(1)}ata yang saya punya", teks, flags=re.IGNORECASE)
# baris penanda pertanyaan lanjutan (lihat bagian "Pertanyaan lanjutan:" di prompt), boleh ditulis tebal
POLA_LANJUTAN = re.compile(r"[ \t]*[*_]{0,2}\[\[\s*lanjutan\s*\]\][*_]{0,2}[ \t]*", re.IGNORECASE)
MAKS_SARAN = 3
PANJANG_SARAN = 120


def pisah_saran(teks):
    """Memisahkan pertanyaan lanjutan sesudah baris [[lanjutan]] dari jawaban, agar tampil sebagai tombol, bukan teks."""
    teks = re.sub(r"<think>.*?</think>", "", teks, flags=re.DOTALL)
    semua = list(POLA_LANJUTAN.finditer(teks))
    if not semua:
        return teks, []
    terakhir = semua[-1]
    saran = []
    for baris in teks[terakhir.end():].split("\n"):
        baris = re.sub(r"^\s*(?:[-*+•]|\d+[.)])\s*", "", baris).strip().strip("\"'*_").strip()
        if baris and len(baris) <= PANJANG_SARAN and baris not in saran:
            saran.append(baris)
    return teks[:terakhir.start()].rstrip(), saran[:MAKS_SARAN]


def hasil(keadaan, teks):
    catatan = keadaan["catatan"]
    # gambar dari rencana pemahaman dicari di latar belakang; ditunggu sebentar agar ikut tampil
    tunggu_gambar(catatan, BATAS_TUNGGU_GAMBAR)
    semua = catatan["sumber"]
    teks, saran = pisah_saran(teks)
    if semua:
        teks = POLA_DAFTAR_SUMBER.sub("", teks).strip()
    gambar_karangan = bool(POLA_GAMBAR_MD.search(re.sub(r"```.*?```", "", teks, flags=re.DOTALL))) and not catatan.get("gambar")
    teks, sumber = rapikan_sitasi(hapus_istilah_internal(bersihkan_format(teks)), semua, catatan["maks_sumber_luar"])
    if gambar_karangan:
        teks += "\n\n*Gambar belum bisa ditampilkan.*"
    sembunyi = set()
    if catatan.get("mode_gambar") == "tiap":
        teks, sembunyi = tempatkan_gambar(teks, catatan.get("rencana_gambar") or [],
                                          lambda daftar: gambar_susulan(catatan, daftar, BATAS_TUNGGU_SUSULAN))
    teks, gambar = rapikan_gambar(teks, [g for g in catatan.get("gambar") or [] if g["kelompok"] not in sembunyi])
    hasil_akhir = {"jawaban": teks, "sumber": sumber, "pakai_internet": any(s["url"] for s in semua)}
    if catatan.get("email"):
        hasil_akhir["email"] = catatan["email"]
    if catatan.get("instruksi"):
        hasil_akhir["instruksi"] = catatan["instruksi"]
    if gambar:
        hasil_akhir["gambar"] = gambar
    if saran:
        hasil_akhir["saran"] = saran
    return hasil_akhir


# Markdown gambar yang ditulis model sendiri; gambar asli datang dari alat cari_gambar, bukan dari teks jawaban
POLA_GAMBAR_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")


MAKS_GAMBAR_TAMPIL = 20
# awal butir yang bisa menjadi tempat gambar: judul, nomor, poin, atau baris yang diawali teks tebal
# jenis butir yang dicoba untuk gambar susulan jika tidak ada butir yang menyebut subjek rencana
URUTAN_JENIS_BUTIR = ("nomor", "tebal", "judul", "poin")
MAKS_HURUF_NAMA_BUTIR = 80
MAKS_KATA_NAMA_BUTIR = 8
POLA_AWAL_BUTIR = re.compile(r"^(#{1,6}\s|\d+(?:\s*(?:,|&|-|–|dan|and)\s*\d+)*[.)]\s|[-*+]\s|\*\*|__)")


def jenis_butir(baris):
    cocok = POLA_AWAL_BUTIR.match(baris)
    if not cocok:
        return None
    awal = cocok.group(1)
    return "judul" if awal[0] == "#" else "nomor" if awal[0].isdigit() else "tebal" if awal in ("**", "__") else "poin"


def subjek_disebut(teks, ciri):
    """Kelompok yang kata pembeda subjeknya disebut di teks, urut sesuai tempat pertama disebut."""
    kecil = POLA_PENANDA_GAMBAR.sub(" ", teks).lower()
    kata = kata_kunci(kecil)
    posisi = {}
    for kelompok, pembeda in ciri.items():
        sama = pembeda & kata
        if sama:
            posisi[kelompok] = min(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", kecil).start() for k in sama)
    return sorted(posisi, key=posisi.get)


def ujung_penjelasan(baris, awal, akhir):
    """Baris terakhir paragraf pertama sesudah judul butir, agar gambar tepat di bawah penjelasannya, bukan di bawah kesimpulan jawaban."""
    i = awal + 1
    while i < akhir and not baris[i].strip():
        i += 1
    if i >= akhir or (baris[i].lstrip().startswith("|") and not baris[awal].lstrip().startswith("|")):
        return awal
    while i + 1 < akhir and baris[i + 1].strip():
        i += 1
    return i


def nama_butir(baris):
    """Nama hal di judul butir, tanpa nomor, tanda Markdown, dan penjelasan sesudah titik dua atau tanda pisah; "" jika bukan nama."""
    teks = POLA_PENANDA_GAMBAR.sub(" ", baris)
    teks = re.sub(r"^\s*(#{1,6}\s+|\d+(?:\s*(?:,|&|-|–|dan|and)\s*\d+)*[.)]\s+|[-*+]\s+)", "", teks)
    teks = re.split(r":\s|:$|\s[—–-]\s", re.sub(r"[*_`]", "", teks))[0].strip(" .")
    if not 3 <= len(teks) <= MAKS_HURUF_NAMA_BUTIR or len(teks.split()) > MAKS_KATA_NAMA_BUTIR or teks.endswith("?"):
        return ""
    return teks


def tempatkan_gambar(teks, rencana, susulan=None):
    """Gambar yang dicari otomatis per subjek ditaruh di butir yang judulnya menyebut nama subjek itu, karena model sering salah
    menulis nomor penanda. Penanda di butir subjek lain, atau di butir lain padahal subjeknya punya butir sendiri, dipindah;
    penanda subjek yang tidak punya butir dibiarkan. Di tabel, penanda di baris yang menyebut subjek lain diganti nomornya.
    susulan(daftar (nama, pembeda)) -> {nama: kelompok} mencari gambar untuk butir sejenis yang belum bergambar, misalnya hal yang
    tidak ada di rencana awal. Mengembalikan teks dan kelompok yang disembunyikan: subjek rencana yang tidak dibahas jawaban,
    jika subjek lain berhasil ditemukan namanya."""
    ciri = ciri_subjek(rencana)
    if not ciri and not susulan:
        return teks, set()
    baris = teks.split("\n")
    di_kode, kode, jenis = False, [], []
    for b in baris:
        if b.lstrip().startswith("```"):
            di_kode = not di_kode
            kode.append(True)
        else:
            kode.append(di_kode)
        jenis.append(None if kode[-1] or b.lstrip().startswith("|") else jenis_butir(b))
    tabel = [i for i, b in enumerate(baris) if not kode[i] and b.lstrip().startswith("|")]

    # butir: dari awal butir sampai awal butir berikutnya yang sejenis, atau judul
    butir = []
    for i, j in enumerate(jenis):
        if j:
            akhir = next((k for k in range(i + 1, len(baris)) if jenis[k] == j or jenis[k] == "judul"), len(baris))
            butir.append((i, akhir, subjek_disebut(baris[i], ciri)))
    ditemukan = {k for _, _, s in butir for k in s} | {k for i in tabel for k in subjek_disebut(baris[i], ciri)}

    for i, b in enumerate(baris):
        if kode[i] or not POLA_PENANDA_GAMBAR.search(b):
            continue
        if i in tabel:
            cocok = subjek_disebut(b, ciri)
            if cocok:
                baris[i] = POLA_PENANDA_GAMBAR.sub(lambda c: c.group(0) if int(c.group(1)) in cocok or int(c.group(1)) not in ciri
                                                   else f"[[gambar:{cocok[0]}]]", b)
            continue
        milik = next((s for a, z, s in reversed(butir) if a <= i < z), None)
        baris[i] = POLA_PENANDA_GAMBAR.sub(lambda c: "" if (int(c.group(1)) in ciri and int(c.group(1)) not in (milik or [])
                                                            and (milik or int(c.group(1)) in ditemukan)) else c.group(0), b)

    sudah = {int(n) for i, b in enumerate(baris) if not kode[i] for n in POLA_PENANDA_GAMBAR.findall(b)}
    sisipan = []
    for a, z, subjek in butir:
        kurang = [k for k in subjek if k not in sudah]
        if kurang:
            sisipan.append((ujung_penjelasan(baris, a, z), kurang))
            sudah.update(kurang)

    if susulan:
        sisipan += butir_susulan(baris, jenis, butir, sisipan, susulan)
    for ujung, kelompok in sorted(sisipan, key=lambda s: -s[0]):
        baris.insert(ujung + 1, "\n".join(f"[[gambar:{k}]]" for k in kelompok))
    sembunyi = set(ciri) - sudah if ditemukan else set()
    return "\n".join(baris), sembunyi


def butir_susulan(baris, jenis, butir, sisipan, susulan):
    """Butir jenis utama (yang menyebut subjek rencana, atau jika tidak ada, jenis daftar terbanyak) yang belum punya gambar
    dicarikan gambar menurut nama di judulnya. Kata pembeda dihitung dari nama semua butir jenis itu."""
    utama = {jenis[a] for a, _, s in butir if s}
    if not utama:
        jumlah = {j: sum(jenis[a] == j for a, _, _ in butir) for j in URUTAN_JENIS_BUTIR}
        utama = {next((j for j in URUTAN_JENIS_BUTIR if jumlah[j] >= 2), None)}
    terisi = {u for u, _ in sisipan}
    calon = [(a, z, nama_butir(baris[a])) for a, z, s in butir if jenis[a] in utama]
    calon = [(a, z, n) for a, z, n in calon if n]
    if len(calon) < 2:
        return []
    ciri = ciri_subjek([(n, a) for a, _, n in calon])
    kosong = [(a, z, n) for a, z, n in calon if not any(POLA_PENANDA_GAMBAR.search(baris[k]) for k in range(a, z))
              and ujung_penjelasan(baris, a, z) not in terisi and not any(s for x, _, s in butir if x == a)]
    hasil = susulan([(n, ciri.get(a)) for a, _, n in kosong])
    return [(ujung_penjelasan(baris, a, z), [hasil[n]]) for a, z, n in kosong if n in hasil]


def rapikan_gambar(teks, gambar):
    """Penanda [[gambar:n]] menampilkan satu gambar kelompok n di tempat itu, misalnya di bawah butir daftar atau di sel tabel:
    gambar terbaik kelompok itu yang belum dipakai butir sebelumnya, karena gambar yang sama di dua butir pasti salah di salah satunya.
    Penanda yang tidak punya gambar seperti itu, atau ditulis ulang, dibuang. Kelompok tanpa penanda tampil di akhir jawaban."""
    dipakai, terpilih, alamat = [], [], set()

    def ganti(cocok):
        nomor = int(cocok.group(1))
        if nomor in dipakai or len(terpilih) >= MAKS_GAMBAR_TAMPIL:
            return ""
        pilihan = next((g for g in gambar if g["kelompok"] == nomor and g["url"] not in alamat), None)
        if pilihan is None:
            return ""
        dipakai.append(nomor)
        terpilih.append(pilihan)
        alamat.add(pilihan["url"])
        return f"[[gambar:{nomor}]]"

    potongan = re.split(r"(```.*?```)", teks, flags=re.DOTALL)
    teks = "".join(p if p.startswith("```") else POLA_PENANDA_GAMBAR.sub(ganti, p) for p in potongan)
    teks = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+\n", "\n", teks)).strip()
    for g in gambar:
        if g["kelompok"] not in dipakai and g["url"] not in alamat:
            terpilih.append(g)
            alamat.add(g["url"])
    return teks, terpilih[:MAKS_GAMBAR_TAMPIL]


def bersihkan_format(teks):
    """Membuang catatan berpikir dan merapikan Markdown: butir "*" jadi "-", judul paling besar ###.
    Tebal, miring, tabel, dan blok grafik dibiarkan karena ditampilkan frontend."""
    teks = re.sub(r"<think>.*?</think>", "", teks, flags=re.DOTALL)
    hasil, di_kode = [], False
    for baris in teks.split("\n"):
        if baris.lstrip().startswith("```"):
            di_kode = not di_kode
        elif not di_kode and baris.strip() == TANDA_DIPERSINGKAT:
            # tanda dari riwayat yang dipersingkat (siapkan.ringkas_teks) tidak boleh ikut tampil
            continue
        elif not di_kode:
            baris = re.sub(r"^\s{0,3}#{1,6}\s+", "### ", baris)
            baris = re.sub(r"^(\s*)[*+]\s+", r"\1- ", baris)
            baris = POLA_GAMBAR_MD.sub("", baris)
        hasil.append(baris)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(satukan_tabel(hasil))).strip()


def satukan_tabel(semua_baris):
    """Baris kosong di antara baris tabel dibuang, karena tabel Markdown terputus oleh baris kosong
    dan sisa barisnya tampil sebagai teks "| a | b |"."""
    hasil, di_kode = [], False
    for i, baris in enumerate(semua_baris):
        if baris.lstrip().startswith("```"):
            di_kode = not di_kode
        if not di_kode and not baris.strip() and hasil and hasil[-1].lstrip().startswith("|"):
            j = next((j for j in range(i + 1, len(semua_baris)) if semua_baris[j].strip()), None)
            # baris berikutnya yang diikuti garis pemisah adalah judul tabel baru, jadi tabelnya tidak disatukan
            tabel_baru = j is not None and j + 1 < len(semua_baris) and POLA_PEMISAH_TABEL.match(semua_baris[j + 1])
            if j is not None and semua_baris[j].lstrip().startswith("|") and not tabel_baru:
                continue
        hasil.append(baris)
    return hasil


def rapikan_sitasi(teks, semua, maks_sumber_luar):
    """Menyisakan sumber luar yang disitasi (jumlahnya dibatasi) dan menomori ulang [n] mulai dari 1.
    Data internal tidak pernah ditampilkan sebagai sumber, jadi nomornya dibuang."""
    dipakai = []

    def ganti(cocok):
        nomor = int(cocok.group(1))
        if not 1 <= nomor <= len(semua) or not semua[nomor - 1]["url"]:
            return ""
        if nomor not in dipakai:
            if len(dipakai) >= maks_sumber_luar:
                return ""
            dipakai.append(nomor)
        return f" [{dipakai.index(nomor) + 1}]"

    teks = POLA_SITASI.sub(ganti, teks).strip()
    # sitasi yang sama berturut-turut, misalnya "[1] [1]", cukup ditulis sekali
    teks = re.sub(r"( \[\d+\])(?:\1)+", r"\1", teks)
    # jawaban tanpa nomor sumber (selera, opini santai, logika) tidak menampilkan daftar sumber walaupun sempat mencari
    return teks, [semua[nomor - 1] for nomor in dipakai]