import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

from pengaman.aturan import GalatPengaman, periksa_url, potong

BATAS_BYTE = 1_000_000
MAKS_PENGALIHAN = 3
JENIS_DIIZINKAN = ("text/html", "text/plain", "application/xhtml+xml")
KODE_PENGALIHAN = (301, 302, 303, 307, 308)


class TanpaPengalihanOtomatis(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PengambilTeks(HTMLParser):
    TAG_DIABAIKAN = {"script", "style", "noscript", "svg", "head", "template"}

    def __init__(self):
        super().__init__()
        self.potongan = []
        self.judul = ""
        self.kedalaman_abaikan = 0
        self.di_judul = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.di_judul = True
        if tag in self.TAG_DIABAIKAN:
            self.kedalaman_abaikan += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.di_judul = False
        if tag in self.TAG_DIABAIKAN and self.kedalaman_abaikan > 0:
            self.kedalaman_abaikan -= 1

    def handle_data(self, data):
        if self.di_judul:
            self.judul += data
        elif self.kedalaman_abaikan == 0:
            self.potongan.append(data)


pembuka = urllib.request.build_opener(TanpaPengalihanOtomatis)


def baca(url, daftar_blokir, batas_waktu):
    """Membuka satu halaman web dengan pemeriksaan keamanan di setiap pengalihan."""
    for _ in range(MAKS_PENGALIHAN + 1):
        periksa_url(url, daftar_blokir)
        permintaan = urllib.request.Request(url, headers={"User-Agent": "LatihanChatbotAgent/1.0"})
        try:
            respon = pembuka.open(permintaan, timeout=batas_waktu)
        except urllib.error.HTTPError as galat:
            if galat.code in KODE_PENGALIHAN and galat.headers.get("Location"):
                url = urljoin(url, galat.headers["Location"])
                continue
            raise GalatPengaman(f"halaman membalas kode {galat.code}")
        break
    else:
        raise GalatPengaman("terlalu banyak pengalihan")

    with respon:
        jenis = respon.headers.get_content_type()
        if jenis not in JENIS_DIIZINKAN:
            raise GalatPengaman(f"jenis konten {jenis} tidak didukung")
        mentah = respon.read(BATAS_BYTE)
        kode_huruf = respon.headers.get_content_charset() or "utf-8"

    teks = mentah.decode(kode_huruf, "replace")
    if jenis == "text/plain":
        return {"url": url, "judul": "", "teks": potong(teks)}

    pengambil = PengambilTeks()
    pengambil.feed(teks)
    return {
        "url": url,
        "judul": " ".join(pengambil.judul.split()),
        "teks": potong(" ".join(pengambil.potongan)),
    }