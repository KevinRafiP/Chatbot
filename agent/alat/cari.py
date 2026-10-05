import json
import urllib.request
from urllib.parse import urlparse

from pengaman.aturan import domain_diblokir, potong

ALAMAT_TAVILY = "https://api.tavily.com/search"


def cari(kueri, api_key, daftar_blokir, batas_waktu, maks_hasil=5):
    """Mencari di internet lewat Tavily dan mengembalikan daftar hasil singkat."""
    badan = {"query": kueri[:300], "max_results": maks_hasil, "search_depth": "basic"}
    permintaan = urllib.request.Request(
        ALAMAT_TAVILY,
        data=json.dumps(badan).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(permintaan, timeout=batas_waktu) as respon:
        data = json.load(respon)

    hasil = []
    for item in data.get("results", []):
        url = item.get("url", "")
        host = urlparse(url).hostname or ""
        if not url or domain_diblokir(host, daftar_blokir):
            continue
        hasil.append({
            "judul": item.get("title", ""),
            "url": url,
            "cuplikan": potong(item.get("content", ""), 800),
        })
    return hasil