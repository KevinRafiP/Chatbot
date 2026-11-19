import http.client
import json
import os
import socket
import time
import threading
import urllib.error
import urllib.parse
import urllib.request

from pengaman.aturan import alamat_umum

BATAS_BYTE = 2_000_000
TAMBAHAN_BATAS_DETIK = 5


class GalatAlat(Exception):
    """Galat yang pesannya aman ditampilkan ke model, misalnya kota tidak ditemukan."""


def agen_wiki():
    """Agen pengguna untuk API wiki; WIKI_KONTAK (alamat situs atau email) dianjurkan aturan Wikimedia agar tidak cepat dibatasi."""
    kontak = os.environ.get("WIKI_KONTAK", "").strip()
    return f"Vokapas/1.0 ({kontak})" if kontak else "Mozilla/5.0 (compatible; Vokapas/1.0)"


class GalatSibuk(GalatAlat):
    """Layanan membalas 429 (terlalu banyak permintaan); boleh dicoba sekali lagi setelah jeda."""


def sambung_umum(alamat, batas_waktu=socket._GLOBAL_DEFAULT_TIMEOUT, alamat_sumber=None):
    """Seperti socket.create_connection, tetapi hanya ke alamat internet umum hasil DNS saat itu juga (seperti tolakAlamatInternal
    di backend), jadi DNS yang berubah setelah periksa_url tidak bisa mengarahkan sambungan ke jaringan internal."""
    host, port = alamat
    *lain, terakhir = alamat_umum(host, port)
    for ip in lain:
        try:
            return socket.create_connection((ip, port), batas_waktu, alamat_sumber)
        except OSError:
            continue
    return socket.create_connection((terakhir, port), batas_waktu, alamat_sumber)


class SambunganAman:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = self.sambung

    def sambung(self, alamat, batas_waktu, alamat_sumber=None):
        # lewat proxy, yang disambung adalah proxy milik pemilik server; tujuannya sudah dicek periksa_url
        if self._tunnel_host:
            return socket.create_connection(alamat, batas_waktu, alamat_sumber)
        return sambung_umum(alamat, batas_waktu, alamat_sumber)


class SambunganHTTPAman(SambunganAman, http.client.HTTPConnection):
    pass


class SambunganHTTPSAman(SambunganAman, http.client.HTTPSConnection):
    pass


class PenanganHTTPAman(urllib.request.HTTPHandler):
    def http_open(self, permintaan):
        return self.do_open(SambunganHTTPAman, permintaan)


class PenanganHTTPSAman(urllib.request.HTTPSHandler):
    def https_open(self, permintaan):
        return self.do_open(SambunganHTTPSAman, permintaan, context=self._context)


# untuk alamat dari internet (halaman, gambar, wiki sumber); API yang memang lokal (misalnya backend) tetap memakai urlopen biasa
pembuka_umum = urllib.request.build_opener(PenanganHTTPAman, PenanganHTTPSAman)


def ambil_json(alamat, parameter=None, batas_waktu=15, agen_pengguna="Vokapas/1.0", metode="GET", badan=None, header=None,
               hanya_umum=False):
    """Memanggil API JSON dan mengembalikan isinya; balasan dibatasi BATAS_BYTE agar memori aman.
    hanya_umum untuk alamat dari internet, agar sambungannya hanya ke alamat umum (lihat sambung_umum)."""
    if parameter:
        alamat = f"{alamat}{'&' if '?' in alamat else '?'}{urllib.parse.urlencode(parameter)}"
    semua_header = {"User-Agent": agen_pengguna, "Accept": "application/json"}
    if badan is not None:
        semua_header["Content-Type"] = "application/json"
        badan = json.dumps(badan).encode("utf-8")
    semua_header.update(header or {})
    permintaan = urllib.request.Request(alamat, data=badan, headers=semua_header, method=metode)
    try:
        isi = unduh_dengan_batas(permintaan, batas_waktu, pembuka_umum.open if hanya_umum else urllib.request.urlopen)
    except urllib.error.HTTPError as galat:
        if galat.code == 404:
            raise GalatAlat("data tidak ditemukan")
        if galat.code == 429:
            raise GalatSibuk("layanan sedang sibuk, coba lagi sebentar lagi")
        raise
    if len(isi) > BATAS_BYTE:
        raise GalatAlat("balasan layanan terlalu besar")
    return json.loads(isi)

def unduh_dengan_batas(permintaan, batas_waktu, buka=urllib.request.urlopen):
    """Mengunduh di benang terpisah dengan batas waktu total. Timeout urlopen hanya berlaku per langkah,
    jadi DNS yang lambat atau server yang membalas sedikit-sedikit bisa membuat agent macet tanpa batas."""
    hasil = {}

    def unduh():
        try:
            with buka(permintaan, timeout=batas_waktu) as respon:
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