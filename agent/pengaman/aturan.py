import ipaddress
import re
import socket
from urllib.parse import urlparse

BATAS_PERTANYAAN = 2000
BATAS_TEKS_WEB = 6000

KATA_MINTA_INTERNET = [
    "internet", "web", "online", "google", "browsing", "telusuri", "searching",
    "cari di", "carikan", "situs", "link", "url", "berita", "terbaru", "terkini",
]

POLA_URL = re.compile(r"https?://\S+", re.IGNORECASE)


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