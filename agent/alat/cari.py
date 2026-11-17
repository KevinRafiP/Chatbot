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
ALAMAT_SERPER_GAMBAR = "https://google.serper.dev/images"
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


def dengan_situs(kueri, domain):
    """Penyedia tanpa filter domain memakai operator site: di kuerinya."""
    return f"{kueri} ({' OR '.join(f'site:{d}' for d in domain)})" if domain else kueri


def cari_tavily(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    """basic = 1 kredit, advanced = 2 kredit."""
    badan = {"query": kueri, "max_results": maks_hasil, "search_depth": kedalaman}
    if domain:
        badan["include_domains"] = list(domain)
    data = kirim(ALAMAT_TAVILY, badan, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    return [(item.get("url", ""), item.get("title", ""), item.get("content", "")) for item in data.get("results", [])]


def cari_exa(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    """Cuplikan diambil dari highlights, yaitu bagian halaman yang paling cocok dengan kueri."""
    badan = {
        "query": kueri,
        "numResults": maks_hasil,
        "type": "auto" if kedalaman == "advanced" else "lite",
        "contents": {"highlights": {"maxCharacters": MAKS_HURUF_CUPLIKAN}},
    }
    if domain:
        badan["includeDomains"] = list(domain)
    data = kirim(ALAMAT_EXA, badan, {"x-api-key": kunci}, batas_waktu)
    return [(item.get("url", ""), item.get("title") or "", " ... ".join(item.get("highlights") or []) or item.get("text") or "")
            for item in data.get("results", [])]


def cari_langsearch(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    data = kirim(ALAMAT_LANGSEARCH, {"query": dengan_situs(kueri, domain), "count": maks_hasil}, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    halaman = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
    return [(item.get("url", ""), item.get("name", ""), item.get("snippet", "")) for item in halaman]


def cari_serper(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    """Hasil Google lewat Serper; cuplikannya pendek (sekitar satu kalimat), jadi model lebih sering perlu baca_url."""
    data = kirim(ALAMAT_SERPER, {"q": dengan_situs(kueri, domain)}, {"X-API-KEY": kunci}, batas_waktu)
    return [(item.get("link", ""), item.get("title", ""), item.get("snippet", "")) for item in (data.get("organic") or [])[:maks_hasil]]


# penyedia baru cukup ditambah di sini: fungsi(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None) -> [(url, judul, cuplikan)];
# domain = daftar situs yang boleh muncul (sumber utama), None = semua situs
PENYEDIA = {"tavily": cari_tavily, "exa": cari_exa, "langsearch": cari_langsearch, "serper": cari_serper}


def gambar_tavily(kueri, kunci, batas_waktu):
    """Gambar dari halaman hasil pencarian; Tavily tidak memberi alamat halamannya."""
    badan = {"query": kueri, "max_results": 3, "search_depth": "basic", "include_images": True, "include_image_descriptions": True}
    data = kirim(ALAMAT_TAVILY, badan, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    hasil = []
    for item in data.get("images") or []:
        if isinstance(item, str):
            hasil.append((item, "", ""))
        elif isinstance(item, dict):
            hasil.append((item.get("url", ""), item.get("description") or "", ""))
    return hasil


def gambar_serper(kueri, kunci, batas_waktu):
    data = kirim(ALAMAT_SERPER_GAMBAR, {"q": kueri}, {"X-API-KEY": kunci}, batas_waktu)
    return [(item.get("imageUrl", ""), item.get("title", ""), item.get("link", "")) for item in data.get("images") or []]


# penyedia yang bisa mencari gambar: fungsi(kueri, kunci, batas_waktu) -> [(url gambar, judul, url halaman)];
# penyedia lain di CARI_PENYEDIA dilewati saat mencari gambar
PENYEDIA_GAMBAR = {"tavily": gambar_tavily, "serper": gambar_serper}


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

    def ada_gambar(self):
        return any(jenis_penyedia(nama) in PENYEDIA_GAMBAR for nama, _ in self.daftar)

    def nama(self):
        return [nama for nama, _ in self.daftar]

    def cari(self, kueri, daftar_blokir, batas_waktu, maks_hasil=5, kedalaman="advanced", domain=None):
        mentah = self.coba(PENYEDIA, lambda fungsi, kunci: fungsi(kueri[:300], kunci, maks_hasil, kedalaman, batas_waktu, domain))
        return saring(mentah, daftar_blokir)

    def cari_gambar(self, kueri, daftar_blokir, batas_waktu):
        mentah = self.coba(PENYEDIA_GAMBAR, lambda fungsi, kunci: fungsi(kueri[:300], kunci, batas_waktu))
        hasil = []
        for url, judul, halaman in mentah:
            if url and not domain_diblokir(urlparse(url).hostname or "", daftar_blokir):
                hasil.append({"url": url, "judul": judul or "", "halaman": halaman or ""})
        return hasil

    def coba(self, peta, panggil):
        """Memanggil penyedia pertama di peta yang belum habis; pindah ke berikutnya jika habis atau sibuk."""
        pertama = True
        for nama, kunci in self.daftar:
            fungsi = peta.get(jenis_penyedia(nama))
            if fungsi is None:
                continue
            with self.gembok:
                if time.monotonic() < self.habis_sampai.get(nama, 0):
                    pertama = False
                    continue
            try:
                mentah = panggil(fungsi, kunci)
            except urllib.error.HTTPError as galat:
                if galat.code in KODE_HABIS | KODE_HABIS_LAIN.get(jenis_penyedia(nama), set()):
                    logging.warning("penyedia cari %s habis atau kuncinya salah (kode %s), pindah ke berikutnya", nama, galat.code)
                    with self.gembok:
                        self.habis_sampai[nama] = time.monotonic() + self.jeda
                    pertama = False
                    continue
                if galat.code in KODE_SIBUK:
                    logging.warning("penyedia cari %s sibuk (kode 429), pindah ke berikutnya", nama)
                    pertama = False
                    continue
                raise
            if not pertama:
                logging.info("pencarian memakai penyedia %s", nama)
            return mentah
        raise GalatHabis("semua penyedia pencarian sedang habis kuotanya atau sibuk")


def saring(mentah, daftar_blokir):
    hasil = []
    for url, judul, cuplikan in mentah:
        host = urlparse(url).hostname or ""
        if not url or domain_diblokir(host, daftar_blokir):
            continue
        hasil.append({"judul": judul, "url": url, "cuplikan": potong(cuplikan, MAKS_HURUF_CUPLIKAN)})
    return hasil
