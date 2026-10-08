import ipaddress
import re
import socket
from urllib.parse import urlparse

BATAS_PERTANYAAN = 2000
BATAS_TEKS_WEB = 3000
SUMBER_BAWAAN = 2
SUMBER_TERBANYAK = 10
TAMBAHAN_DARI_MINIMAL = 3

KATA_MINTA_INTERNET = [
    "internet", "web", "online", "google", "browsing", "telusuri", "searching",
    "cari di", "carikan", "situs", "link", "url", "berita", "terbaru", "terkini",
]

POLA_URL = re.compile(r"https?://\S+", re.IGNORECASE)

POLA_KATA_SUMBER = re.compile(r"\b(sumber|referensi|rujukan|link|tautan)")
POLA_MINIMAL = re.compile(r"\b(?:minimal|minimum|min|paling sedikit|setidaknya|sedikitnya)\.?\s*(\d{1,2})\b")
POLA_MAKSIMAL = re.compile(r"\b(?:maksimal|maksimum|maks|max|paling banyak)\.?\s*(\d{1,2})\b")
POLA_JUMLAH = re.compile(r"\b(\d{1,2})\s*(?:sumber|referensi|rujukan|link|tautan)")

POLA_MERUSAK = [re.compile(pola) for pola in (
    r"\b(abaikan|lupakan|hiraukan|ignore|disregard|forget)\b.{0,40}\b(instruksi|perintah|aturan|arahan|instructions?|rules?|prompt)\b",
    r"\b(system prompt|prompt sistem|instruksi sistem)\b",
    r"\b(drop|truncate)\s+(table|database)\b",
    r"\bdelete\s+from\b",
    r"\brm\s+-rf\b",
    r"\b(hapus|kosongkan|rusak|hancurkan|musnahkan)\b.{0,40}\b(database|basis data|tabel|sistem|server|algoritma|semua data|seluruh data)\b",
    r"\b(matikan|nonaktifkan|lewati|bypass)\b.{0,40}\b(pengaman|filter|batasan|aturan|guard ?rail)\b",
    r"\b(jailbreak|developer mode|mode pengembang)\b",
)]


class GalatPengaman(Exception):
    pass


def periksa_pertanyaan(teks):
    teks = (teks or "").strip()
    if not teks:
        raise GalatPengaman("pertanyaan wajib diisi")
    if len(teks) > BATAS_PERTANYAAN:
        raise GalatPengaman(f"pertanyaan maksimal {BATAS_PERTANYAAN} karakter")
    return teks


def minta_internet(teks):
    """True jika pengguna jelas meminta sesuatu dari internet."""
    kecil = teks.lower()
    if POLA_URL.search(kecil):
        return True
    return any(kata in kecil for kata in KATA_MINTA_INTERNET)

def permintaan_merusak(teks):
    """True jika pesan berusaha membatalkan aturan agent atau merusak data dan sistem."""
    kecil = teks.lower()
    return any(pola.search(kecil) for pola in POLA_MERUSAK)


def batas_sumber(teks):
    """Membaca permintaan jumlah sumber luar dan mengembalikan (minimal, maksimal)."""
    kecil = teks.lower()
    if not POLA_KATA_SUMBER.search(kecil):
        return 0, SUMBER_BAWAAN

    minimal = angka_pertama(POLA_MINIMAL, kecil)
    maksimal = angka_pertama(POLA_MAKSIMAL, kecil)
    if minimal is None and maksimal is None:
        maksimal = angka_pertama(POLA_JUMLAH, kecil)
    if maksimal is None:
        maksimal = SUMBER_BAWAAN if minimal is None else minimal + TAMBAHAN_DARI_MINIMAL

    maksimal = max(1, min(maksimal, SUMBER_TERBANYAK))
    return min(minimal or 0, maksimal), maksimal


def angka_pertama(pola, teks):
    cocok = pola.search(teks)
    return int(cocok.group(1)) if cocok else None

def domain_diblokir(host, daftar_blokir):
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in daftar_blokir)


def periksa_url(url, daftar_blokir):
    """Menolak URL yang bukan http/https, port aneh, domain terlarang, atau mengarah ke jaringan internal."""
    bagian = urlparse(url)
    if bagian.scheme not in ("http", "https"):
        raise GalatPengaman("hanya alamat http/https yang diizinkan")
    if not bagian.hostname:
        raise GalatPengaman("alamat tidak valid")
    if bagian.port not in (None, 80, 443):
        raise GalatPengaman("port tidak diizinkan")
    if bagian.username or bagian.password:
        raise GalatPengaman("alamat berisi login tidak diizinkan")
    if domain_diblokir(bagian.hostname, daftar_blokir):
        raise GalatPengaman("domain diblokir")

    try:
        alamat_ip = {info[4][0] for info in socket.getaddrinfo(bagian.hostname, None)}
    except socket.gaierror:
        raise GalatPengaman("domain tidak ditemukan")

    for ip in alamat_ip:
        if not ipaddress.ip_address(ip.split("%")[0]).is_global:
            raise GalatPengaman("alamat jaringan internal tidak diizinkan")
    return url


def potong(teks, batas=BATAS_TEKS_WEB):
    teks = " ".join(teks.split())
    return teks if len(teks) <= batas else teks[:batas] + " ...(dipotong)"