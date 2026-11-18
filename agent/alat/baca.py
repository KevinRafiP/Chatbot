import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from pengaman.aturan import BATAS_TEKS_WEB, GalatPengaman, periksa_url, potong

BATAS_BYTE = 1_000_000
MAKS_PENGALIHAN = 3
JENIS_DIIZINKAN = ("text/html", "text/plain", "application/xhtml+xml")
KODE_PENGALIHAN = (301, 302, 303, 307, 308)
# gambar halaman dicatat untuk memilih foto dari sumber jawaban sendiri (lihat gambar_web.gambar_sumber)
MAKS_GAMBAR_HALAMAN = 60
MAKS_HURUF_KETERANGAN = 200


class TanpaPengalihanOtomatis(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PengambilTeks(HTMLParser):
    TAG_DIABAIKAN = {"script", "style", "noscript", "svg", "head", "template"}
    # gambar di menu, kepala, kaki, dan samping halaman biasanya logo, ikon, atau tautan artikel lain
    TAG_PINGGIR = {"nav", "header", "footer", "aside"}
    TAG_JUDUL_BAGIAN = {"h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.potongan = []
        self.judul = ""
        self.kedalaman_abaikan = 0
        self.di_judul = False
        self.gambar = []
        self.gambar_utama = ""
        self.kedalaman_pinggir = 0
        self.bagian = ""
        self.judul_bagian = None
        self.keterangan = None
        self.awal_figur = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.di_judul = True
        if tag in self.TAG_DIABAIKAN:
            self.kedalaman_abaikan += 1
        if tag in self.TAG_PINGGIR:
            self.kedalaman_pinggir += 1
        if tag in self.TAG_JUDUL_BAGIAN:
            self.judul_bagian = ""
        elif tag == "figure":
            self.awal_figur.append(len(self.gambar))
        elif tag == "figcaption":
            self.keterangan = ""
        elif tag == "meta":
            self.catat_meta(dict(attrs))
        elif tag == "img" and self.kedalaman_pinggir == 0:
            self.catat_gambar(dict(attrs))

    def handle_endtag(self, tag):
        if tag == "title":
            self.di_judul = False
        if tag in self.TAG_DIABAIKAN and self.kedalaman_abaikan > 0:
            self.kedalaman_abaikan -= 1
        if tag in self.TAG_PINGGIR and self.kedalaman_pinggir > 0:
            self.kedalaman_pinggir -= 1
        if tag in self.TAG_JUDUL_BAGIAN and self.judul_bagian is not None:
            self.bagian = " ".join(self.judul_bagian.split())[:MAKS_HURUF_KETERANGAN]
            self.judul_bagian = None
        elif tag == "figcaption" and self.keterangan is not None:
            # keterangan figur berlaku untuk gambar di dalam figur itu
            teks = " ".join(self.keterangan.split())[:MAKS_HURUF_KETERANGAN]
            for gambar in self.gambar[self.awal_figur[-1] if self.awal_figur else -1:]:
                gambar["keterangan"] = teks
            self.keterangan = None
        elif tag == "figure" and self.awal_figur:
            self.awal_figur.pop()

    def handle_data(self, data):
        if self.di_judul:
            self.judul += data
        elif self.kedalaman_abaikan == 0:
            self.potongan.append(data)
        if self.judul_bagian is not None:
            self.judul_bagian += data
        if self.keterangan is not None:
            self.keterangan += data

    def catat_meta(self, atribut):
        jenis = (atribut.get("property") or atribut.get("name") or "").lower()
        if jenis in ("og:image", "twitter:image") and not self.gambar_utama:
            self.gambar_utama = (atribut.get("content") or "").strip()

    def catat_gambar(self, atribut):
        """Gambar yang dimuat malas menaruh alamat aslinya di data-src atau srcset, bukan di src."""
        alamat = ""
        for nama in ("data-src", "data-lazy-src", "data-original", "src", "data-srcset", "srcset"):
            nilai = (atribut.get(nama) or "").strip()
            if nama.endswith("srcset"):
                nilai = nilai.split(",")[-1].strip().split(" ")[0] if nilai else ""
            if nilai and not nilai.startswith("data:"):
                alamat = nilai
                break
        if not alamat or len(self.gambar) >= MAKS_GAMBAR_HALAMAN or any(g["url"] == alamat for g in self.gambar):
            return
        ukuran = [int(atribut[n]) for n in ("width", "height") if (atribut.get(n) or "").isdigit()]
        self.gambar.append({"url": alamat, "alt": " ".join(f"{atribut.get('alt') or ''} {atribut.get('title') or ''}".split()),
                            "bagian": self.bagian, "keterangan": "", "ukuran": min(ukuran) if ukuran else 0})


pembuka = urllib.request.build_opener(TanpaPengalihanOtomatis)


def baca(url, daftar_blokir, batas_waktu, batas_huruf=BATAS_TEKS_WEB):
    """Membuka satu halaman web dengan pemeriksaan keamanan di setiap pengalihan; teksnya dipotong di batas_huruf."""
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
        return {"url": url, "judul": "", "teks": potong(teks, batas_huruf)}

    pengambil = PengambilTeks()
    pengambil.feed(teks)
    gambar = []
    for item in pengambil.gambar:
        alamat = urljoin(url, item["url"])
        if urlparse(alamat).scheme in ("http", "https"):
            gambar.append({**item, "url": alamat})
    utama = urljoin(url, pengambil.gambar_utama) if pengambil.gambar_utama else ""
    return {
        "url": url,
        "judul": " ".join(pengambil.judul.split()),
        "teks": potong(" ".join(pengambil.potongan), batas_huruf),
        "gambar": gambar,
        "gambar_utama": utama if urlparse(utama).scheme in ("http", "https") else "",
    }