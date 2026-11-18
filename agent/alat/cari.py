import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse

from pengaman.aturan import domain_diblokir, potong

ALAMAT_TAVILY = "https://api.tavily.com/search"
ALAMAT_EXA = "https://api.exa.ai/search"
ALAMAT_LANGSEARCH = "https://api.langsearch.com/v1/web-search"
ALAMAT_SERPER = "https://google.serper.dev/search"
ALAMAT_SERPER_GAMBAR = "https://google.serper.dev/images"
ALAMAT_FIRECRAWL = "https://api.firecrawl.dev/v2/search"
ALAMAT_HASDATA = "https://api.hasdata.com/scrape/google/serp"
ALAMAT_HASDATA_GAMBAR = "https://api.hasdata.com/scrape/google/images"
ALAMAT_BRIGHTDATA = "https://api.brightdata.com/request"
MAKS_HURUF_CUPLIKAN = 1500
# kunci salah atau kredit habis: penyedia dilewati sampai jedanya lewat
KODE_HABIS = {401, 402, 432, 433}
# kode habis tambahan per penyedia; Serper belum mendokumentasikan kode kredit habis, diduga 400 atau 403;
# HasData memakai 403 untuk kredit habis; Bright Data membalas 401 atau 403 untuk kunci atau zona yang salah
KODE_HABIS_LAIN = {"serper": {400, 403}, "hasdata": {403}, "brightdata": {403}}
# kuota gratisnya tidak diisi ulang tiap bulan, jadi selalu dicoba paling akhir apa pun urutan di CARI_PENYEDIA
PENYEDIA_TERAKHIR = {"serper"}
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


def ambil_json(alamat, parameter, kepala, batas_waktu):
    permintaan = urllib.request.Request(f"{alamat}?{urlencode(parameter)}", headers={"User-Agent": "Vokapas/1.0", **kepala})
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


def cari_firecrawl(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    """2 kredit per 10 hasil; cuplikannya berupa deskripsi halaman."""
    badan = {"query": kueri[:500], "limit": maks_hasil, "sources": ["web"]}
    if domain:
        badan["includeDomains"] = list(domain)
    data = kirim(ALAMAT_FIRECRAWL, badan, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    return [(item.get("url", ""), item.get("title") or "", item.get("description") or "") for item in (data.get("data") or {}).get("web") or []]


def cari_hasdata(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    """Hasil Google lewat HasData, 10 kredit per permintaan."""
    data = ambil_json(ALAMAT_HASDATA, {"q": dengan_situs(kueri, domain)}, {"x-api-key": kunci}, batas_waktu)
    return [(item.get("link", ""), item.get("title", ""), item.get("snippet", "")) for item in (data.get("organicResults") or [])[:maks_hasil]]


def minta_brightdata(kunci, parameter, batas_waktu):
    """kunci Bright Data berisi (token, zona); hasil Google dibaca dalam bentuk JSON ringkas (parsed_light)."""
    token, zona = kunci
    badan = {"zone": zona, "url": f"https://www.google.com/search?{urlencode(parameter)}", "format": "raw", "data_format": "parsed_light"}
    return kirim(ALAMAT_BRIGHTDATA, badan, {"Authorization": f"Bearer {token}"}, batas_waktu)


def cari_brightdata(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None):
    data = minta_brightdata(kunci, {"q": dengan_situs(kueri, domain)}, batas_waktu)
    return [(item.get("link", ""), item.get("title", ""), item.get("description", "")) for item in (data.get("organic") or [])[:maks_hasil]]


# penyedia baru cukup ditambah di sini: fungsi(kueri, kunci, maks_hasil, kedalaman, batas_waktu, domain=None) -> [(url, judul, cuplikan)];
# domain = daftar situs yang boleh muncul (sumber utama), None = semua situs
PENYEDIA = {"tavily": cari_tavily, "exa": cari_exa, "langsearch": cari_langsearch, "serper": cari_serper, "firecrawl": cari_firecrawl,
            "hasdata": cari_hasdata, "brightdata": cari_brightdata}


def gambar_tavily(kueri, kunci, batas_waktu):
    """Gambar dari halaman hasil pencarian; Tavily tidak memberi alamat halamannya."""
    badan = {"query": kueri, "max_results": 5, "search_depth": "basic", "include_images": True, "include_image_descriptions": True}
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


def gambar_exa(kueri, kunci, batas_waktu):
    """Exa tidak punya pencarian gambar, jadi yang dipakai gambar utama halaman hasil pencarian dan beberapa gambar di dalamnya;
    judul halaman menjadi keterangannya. Tipe lite tidak menerima extras, jadi memakai auto."""
    badan = {"query": kueri, "numResults": 5, "type": "auto", "contents": {"extras": {"imageLinks": 2}}}
    data = kirim(ALAMAT_EXA, badan, {"x-api-key": kunci}, batas_waktu)
    hasil = []
    for item in data.get("results") or []:
        semua = [item.get("image") or ""] + list((item.get("extras") or {}).get("imageLinks") or [])
        hasil += [(alamat, item.get("title") or "", item.get("url", "")) for alamat in semua if isinstance(alamat, str) and alamat]
    return hasil


def gambar_firecrawl(kueri, kunci, batas_waktu):
    data = kirim(ALAMAT_FIRECRAWL, {"query": kueri[:500], "limit": 10, "sources": ["images"]}, {"Authorization": f"Bearer {kunci}"}, batas_waktu)
    return [(item.get("imageUrl", ""), item.get("title") or "", item.get("url", "")) for item in (data.get("data") or {}).get("images") or []]


def gambar_hasdata(kueri, kunci, batas_waktu):
    data = ambil_json(ALAMAT_HASDATA_GAMBAR, {"q": kueri}, {"x-api-key": kunci}, batas_waktu)
    return [(item.get("original", ""), item.get("title", ""), item.get("link", "")) for item in data.get("imagesResults") or []]


def gambar_brightdata(kueri, kunci, batas_waktu):
    """udm=2 adalah tab Gambar Google."""
    data = minta_brightdata(kunci, {"q": kueri, "udm": 2}, batas_waktu)
    return [(item.get("original_image", ""), item.get("title", ""), item.get("link", "")) for item in data.get("images") or []]


# penyedia yang bisa mencari gambar: fungsi(kueri, kunci, batas_waktu) -> [(url gambar, judul, url halaman)];
# penyedia lain di CARI_PENYEDIA dilewati saat mencari gambar
PENYEDIA_GAMBAR = {"tavily": gambar_tavily, "exa": gambar_exa, "firecrawl": gambar_firecrawl, "hasdata": gambar_hasdata,
                   "brightdata": gambar_brightdata, "serper": gambar_serper}


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
        self.daftar.sort(key=lambda penyedia: jenis_penyedia(penyedia[0]) in PENYEDIA_TERAKHIR)
        self.jeda = jeda_detik
        self.habis_sampai = {}
        self.gembok = threading.Lock()

    def ada(self):
        return bool(self.daftar)

    def ada_gambar(self):
        return any(jenis_penyedia(nama) in PENYEDIA_GAMBAR for nama, _ in self.daftar)

    def nama(self):
        return [nama for nama, _ in self.daftar]

    def nama_gambar(self):
        return [nama for nama, _ in self.daftar if jenis_penyedia(nama) in PENYEDIA_GAMBAR]

    def cari(self, kueri, daftar_blokir, batas_waktu, maks_hasil=5, kedalaman="advanced", domain=None):
        mentah = self.coba(PENYEDIA, lambda fungsi, kunci: fungsi(kueri[:300], kunci, maks_hasil, kedalaman, batas_waktu, domain))
        return saring(mentah, daftar_blokir)

    def cari_gambar(self, kueri, daftar_blokir, batas_waktu, cocok=None):
        """cocok(daftar gambar) False berarti tidak ada gambar yang dipakai, jadi penyedia berikutnya dicoba."""
        def ubah(mentah):
            return [{"url": url, "judul": judul or "", "halaman": halaman or ""} for url, judul, halaman in mentah
                    if url and not domain_diblokir(urlparse(url).hostname or "", daftar_blokir)]
        cukup = (lambda mentah: cocok(ubah(mentah))) if cocok else None
        return ubah(self.coba(PENYEDIA_GAMBAR, lambda fungsi, kunci: fungsi(kueri[:300], kunci, batas_waktu), cukup))

    def coba(self, peta, panggil, cukup=None):
        """Memanggil penyedia pertama di peta yang belum habis; pindah ke berikutnya jika habis atau sibuk.
        cukup(hasil) False juga membuat penyedia berikutnya dicoba, kecuali penyedia terakhir (Serper) yang kuotanya tidak pulih;
        jika tidak ada yang cukup, hasil pertama dikembalikan."""
        pertama = True
        cadangan = None
        for nama, kunci in self.daftar:
            fungsi = peta.get(jenis_penyedia(nama))
            if fungsi is None:
                continue
            if cadangan is not None and jenis_penyedia(nama) in PENYEDIA_TERAKHIR:
                break
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
            if cukup and not cukup(mentah):
                logging.info("hasil penyedia %s tidak ada yang cocok, coba penyedia berikutnya", nama)
                cadangan = mentah if cadangan is None else cadangan
                pertama = False
                continue
            if not pertama:
                logging.info("pencarian memakai penyedia %s", nama)
            return mentah
        if cadangan is not None:
            return cadangan
        raise GalatHabis("semua penyedia pencarian sedang habis kuotanya atau sibuk")


def saring(mentah, daftar_blokir):
    hasil = []
    for url, judul, cuplikan in mentah:
        host = urlparse(url).hostname or ""
        if not url or domain_diblokir(host, daftar_blokir):
            continue
        hasil.append({"judul": judul, "url": url, "cuplikan": potong(cuplikan, MAKS_HURUF_CUPLIKAN)})
    return hasil
