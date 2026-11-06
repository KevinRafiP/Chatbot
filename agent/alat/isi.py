import logging
import re
from concurrent.futures import ThreadPoolExecutor

from alat.baca import baca

# halaman dipotong per bagian; bagian yang paling banyak memuat kata pertanyaan yang dikirim ke model
HURUF_PER_BAGIAN = 700
HURUF_TUMPANG = 100
# halaman panjang (wiki) dibaca lebih banyak daripada baca_url biasa, karena yang dikirim ke model hanya bagian relevannya
BATAS_HURUF_HALAMAN = 60000
MAKS_BAGIAN = 3
KATA_UMUM = {"apa", "itu", "yang", "dan", "atau", "ada", "berapa", "siapa", "bagaimana", "kenapa", "mengapa", "dari", "dengan", "untuk",
             "dalam", "tentang", "ini", "saja", "juga", "akan", "pada", "ke", "di", "the", "and", "what", "who", "how", "for", "of", "in",
             "is", "are", "to", "a", "an"}


def kata_kunci(teks):
    return {k for k in re.findall(r"\w+", (teks or "").lower()) if len(k) >= 3 and k not in KATA_UMUM}


def pecah(teks):
    """Memotong teks menjadi bagian sepanjang HURUF_PER_BAGIAN dengan sedikit tumpang tindih, dipotong di batas kata."""
    teks = " ".join(teks.split())
    bagian, mulai = [], 0
    while mulai < len(teks):
        akhir = min(mulai + HURUF_PER_BAGIAN, len(teks))
        if akhir < len(teks):
            spasi = teks.rfind(" ", mulai + HURUF_PER_BAGIAN // 2, akhir)
            akhir = spasi if spasi > 0 else akhir
        bagian.append((mulai, teks[mulai:akhir]))
        if akhir >= len(teks):
            break
        # bagian berikutnya mulai sedikit sebelum akhir bagian ini, tepat di awal kata
        spasi = teks.find(" ", akhir - HURUF_TUMPANG, akhir)
        mulai = spasi + 1 if spasi > mulai else max(akhir - HURUF_TUMPANG, mulai + 1)
    return bagian


def skor(bagian, kunci, nama):
    kata = re.findall(r"\w+", bagian.lower())
    ada = set(kata) & kunci
    # kata berbeda paling penting, nama (huruf kapital di pertanyaan) dihitung dua kali, kemunculan berulang hanya tambahan kecil
    return len(ada) * 3 + len(ada & nama) * 3 + min(sum(1 for k in kata if k in kunci), 20) * 0.2


def bagian_relevan(teks, kunci, nama, maks_huruf):
    """Bagian halaman yang paling cocok dengan kata kunci, urut sesuai posisinya di halaman."""
    if not teks or not kunci:
        return ""
    calon = sorted(pecah(teks), key=lambda b: skor(b[1], kunci, nama), reverse=True)
    terpilih, panjang = [], 0
    for mulai, isi in calon[:MAKS_BAGIAN * 3]:
        if len(terpilih) >= MAKS_BAGIAN or panjang + len(isi) > maks_huruf or skor(isi, kunci, nama) <= 0:
            continue
        if any(abs(mulai - m) < HURUF_PER_BAGIAN for m, _ in terpilih):
            continue
        terpilih.append((mulai, isi))
        panjang += len(isi)
    return " ... ".join(isi for _, isi in sorted(terpilih))


def baca_isi(hasil, jumlah, teks_tanya, maks_huruf, daftar_blokir, batas_waktu):
    """Membuka beberapa halaman hasil cari_web bersamaan lalu mengisi item["isi"] dengan bagian yang paling relevan.
    item["teks_penuh"] menyimpan teks halaman untuk bukti verifikasi. Halaman yang gagal dibuka tetap memakai cuplikan."""
    if jumlah <= 0 or not hasil:
        return
    # sumber utama dibuka lebih dulu, sumber lemah (video, forum, media sosial) tidak dibuka
    calon = sorted((i for i in hasil if i.get("tingkat") != "lemah"), key=lambda i: not i.get("utama"))[:jumlah]
    if not calon:
        return
    kunci = kata_kunci(teks_tanya)
    nama = kata_kunci(" ".join(re.findall(r"(?<=\s)[A-Z]\w*", " " + (teks_tanya or ""))))

    def buka(item):
        try:
            return item, baca(item["url"], daftar_blokir, batas_waktu, BATAS_HURUF_HALAMAN)
        except Exception as galat:
            logging.info("baca isi %s gagal: %s", item["url"], galat)
            return item, None

    with ThreadPoolExecutor(max_workers=len(calon)) as pelaksana:
        for item, halaman in pelaksana.map(buka, calon):
            if not halaman or not halaman.get("teks"):
                continue
            isi = bagian_relevan(halaman["teks"], kunci, nama, maks_huruf)
            if isi:
                item["isi"] = isi
                item["teks_penuh"] = halaman["teks"]