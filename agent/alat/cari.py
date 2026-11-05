import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from pengaman.aturan import domain_diblokir, potong

ALAMAT_TAVILY = "https://api.tavily.com/search"
ALAMAT_EXA = "https://api.exa.ai/search"
ALAMAT_LANGSEARCH = "https://api.langsearch.com/v1/web-search"
ALAMAT_SERPER = "https://google.serper.dev/search"
MAKS_HURUF_CUPLIKAN = 1500
# kunci salah atau kredit habis: penyedia dilewati sampai jedanya lewat
KODE_HABIS = {401, 402, 432, 433}
# kode habis tambahan per penyedia; Serper belum mendokumentasikan kode kredit habis, diduga 400 atau 403
KODE_HABIS_LAIN = {"serper": {400, 403}}
# terlalu banyak permintaan: penyedia dilewati untuk permintaan ini saja
KODE_SIBUK = {429}


class GalatHabis(Exception):
    pass


def kirim(alamat, badan, kepala, batas_waktu):
    permintaan = urllib.request.Request(
        alamat,
        data=json.dumps(badan).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Vokapas/1.0", **kepala},
        method="POST",
    )
    with urllib.request.urlopen(permintaan, timeout=batas_waktu) as respon:
        return json.load(respon)


def cari_tavily(kueri, kunci, maks_hasil, kedalaman, batas_waktu):
    """basic = 1 kredit, advanced = 2 kredit."""
    data = kirim(ALAMAT_TAVILY, {"query": kueri, "max_results": maks_hasil, "search_depth": kedalaman},
                 {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    return [(item.get("url", ""), item.get("title", ""), item.get("content", "")) for item in data.get("results", [])]


def cari_exa(kueri, kunci, maks_hasil, kedalaman, batas_waktu):
    """Cuplikan diambil dari highlights, yaitu bagian halaman yang paling cocok dengan kueri."""
    badan = {
        "query": kueri,
        "numResults": maks_hasil,
        "type": "auto" if kedalaman == "advanced" else "lite",
        "contents": {"highlights": {"maxCharacters": MAKS_HURUF_CUPLIKAN}},
    }
    data = kirim(ALAMAT_EXA, badan, {"x-api-key": kunci}, batas_waktu)
    return [(item.get("url", ""), item.get("title") or "", " ... ".join(item.get("highlights") or []) or item.get("text") or "")
            for item in data.get("results", [])]


def cari_langsearch(kueri, kunci, maks_hasil, kedalaman, batas_waktu):
    data = kirim(ALAMAT_LANGSEARCH, {"query": kueri, "count": maks_hasil}, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    halaman = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
    return [(item.get("url", ""), item.get("name", ""), item.get("snippet", "")) for item in halaman]


def cari_serper(kueri, kunci, maks_hasil, kedalaman, batas_waktu):
    """Hasil Google lewat Serper; cuplikannya pendek (sekitar satu kalimat), jadi model lebih sering perlu baca_url."""
    data = kirim(ALAMAT_SERPER, {"q": kueri}, {"X-API-KEY": kunci}, batas_waktu)
    return [(item.get("link", ""), item.get("title", ""), item.get("snippet", "")) for item in (data.get("organic") or [])[:maks_hasil]]


# penyedia baru cukup ditambah di sini: fungsi(kueri, kunci, maks_hasil, kedalaman, batas_waktu) -> [(url, judul, cuplikan)]
PENYEDIA = {"tavily": cari_tavily, "exa": cari_exa, "langsearch": cari_langsearch, "serper": cari_serper}


def jenis_penyedia(nama):
    """exa_2 tetap memakai fungsi exa, jadi satu penyedia boleh punya beberapa akun."""
    return re.sub(r"_\d+$", "", nama)


class PencariBerantai:
    """Mencoba penyedia sesuai urutan CARI_PENYEDIA. Penyedia berikutnya hanya dipakai jika penyedia sebelumnya habis atau sibuk."""

    def __init__(self, daftar, jeda_detik):
        self.daftar = []
        for nama, kunci in daftar:
            if jenis_penyedia(nama) in PENYEDIA:
                self.daftar.append((nama, kunci))
            else:
                logging.warning("penyedia cari %s tidak dikenal, dilewati", nama)
        self.jeda = jeda_detik
        self.habis_sampai = {}
        self.gembok = threading.Lock()

    def ada(self):
        return bool(self.daftar)

    def nama(self):
        return [nama for nama, _ in self.daftar]

    def cari(self, kueri, daftar_blokir, batas_waktu, maks_hasil=5, kedalaman="advanced"):
        for nama, kunci in self.daftar:
            with self.gembok:
                if time.monotonic() < self.habis_sampai.get(nama, 0):
                    continue
            try:
                mentah = PENYEDIA[jenis_penyedia(nama)](kueri[:300], kunci, maks_hasil, kedalaman, batas_waktu)
            except urllib.error.HTTPError as galat:
                if galat.code in KODE_HABIS | KODE_HABIS_LAIN.get(jenis_penyedia(nama), set()):
                    logging.warning("penyedia cari %s habis atau kuncinya salah (kode %s), pindah ke berikutnya", nama, galat.code)
                    with self.gembok:
                        self.habis_sampai[nama] = time.monotonic() + self.jeda
                    continue
                if galat.code in KODE_SIBUK:
                    logging.warning("penyedia cari %s sibuk (kode 429), pindah ke berikutnya", nama)
                    continue
                raise
            if nama != self.daftar[0][0]:
                logging.info("cari_web memakai penyedia %s", nama)
            return saring(mentah, daftar_blokir)
        raise GalatHabis("semua penyedia pencarian sedang habis kuotanya atau sibuk")


def saring(mentah, daftar_blokir):
    hasil = []
    for url, judul, cuplikan in mentah:
        host = urlparse(url).hostname or ""
        if not url or domain_diblokir(host, daftar_blokir):
            continue
        hasil.append({"judul": judul, "url": url, "cuplikan": potong(cuplikan, MAKS_HURUF_CUPLIKAN)})
    return hasil
