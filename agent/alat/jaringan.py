import json
import time
import threading
import urllib.error
import urllib.parse
import urllib.request

BATAS_BYTE = 2_000_000
TAMBAHAN_BATAS_DETIK = 5


class GalatAlat(Exception):
    """Galat yang pesannya aman ditampilkan ke model, misalnya kota tidak ditemukan."""


def ambil_json(alamat, parameter=None, batas_waktu=15, agen_pengguna="Vokapas/1.0", metode="GET", badan=None, header=None):
    """Memanggil API JSON dan mengembalikan isinya; balasan dibatasi BATAS_BYTE agar memori aman."""
    if parameter:
        alamat = f"{alamat}{'&' if '?' in alamat else '?'}{urllib.parse.urlencode(parameter)}"
    semua_header = {"User-Agent": agen_pengguna, "Accept": "application/json"}
    if badan is not None:
        semua_header["Content-Type"] = "application/json"
        badan = json.dumps(badan).encode("utf-8")
    semua_header.update(header or {})
    permintaan = urllib.request.Request(alamat, data=badan, headers=semua_header, method=metode)
    try:
        isi = unduh_dengan_batas(permintaan, batas_waktu)
    except urllib.error.HTTPError as galat:
        if galat.code == 404:
            raise GalatAlat("data tidak ditemukan")
        if galat.code == 429:
            raise GalatAlat("layanan sedang sibuk, coba lagi sebentar lagi")
        raise
    if len(isi) > BATAS_BYTE:
        raise GalatAlat("balasan layanan terlalu besar")
    return json.loads(isi)

def unduh_dengan_batas(permintaan, batas_waktu):
    """Mengunduh di benang terpisah dengan batas waktu total. Timeout urlopen hanya berlaku per langkah,
    jadi DNS yang lambat atau server yang membalas sedikit-sedikit bisa membuat agent macet tanpa batas."""
    hasil = {}

    def unduh():
        try:
            with urllib.request.urlopen(permintaan, timeout=batas_waktu) as respon:
                hasil["isi"] = respon.read(BATAS_BYTE + 1)
        except Exception as galat:
            hasil["galat"] = galat

    benang = threading.Thread(target=unduh, daemon=True)
    benang.start()
    benang.join(batas_waktu + TAMBAHAN_BATAS_DETIK)
    if benang.is_alive():
        raise GalatAlat("layanan tidak membalas, coba lagi nanti")
    if "galat" in hasil:
        raise hasil["galat"]
    return hasil["isi"]

class CacheSingkat:
    """Cache kecil di memori untuk data yang jarang berubah (kurs, daftar wilayah), agar API luar tidak dipanggil terus."""

    def __init__(self, detik, maks=200):
        self.detik = detik
        self.maks = maks
        self.isi = {}
        self.kunci = threading.Lock()

    def ambil_atau_buat(self, kunci, buat):
        sekarang = time.monotonic()
        with self.kunci:
            simpanan = self.isi.get(kunci)
            if simpanan and sekarang - simpanan[0] < self.detik:
                return simpanan[1]
        nilai = buat()
        with self.kunci:
            if len(self.isi) >= self.maks:
                self.isi.pop(next(iter(self.isi)))
            self.isi[kunci] = (sekarang, nilai)
        return nilai