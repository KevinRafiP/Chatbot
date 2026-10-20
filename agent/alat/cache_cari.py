import re
import threading
import time

# kueri tentang waktu, harga, atau skor tidak disimpan karena hasilnya cepat basi
POLA_CEPAT_BASI = re.compile(
    r"\b(hari ini|sekarang|saat ini|terbaru|terkini|live|skor|klasemen|harga|cuaca|kurs|berita"
    r"|today|now|latest|current|score|standings|price|weather|news)\b"
)


class CacheCari:
    """Menyimpan hasil cari_web di memori agar kueri yang sama tidak memakai kredit Tavily lagi.
    Isinya hilang saat layanan restart atau tidur; masa_detik 0 berarti cache mati."""

    def __init__(self, masa_detik, maks_isi):
        self.masa = masa_detik
        self.maks_isi = maks_isi
        self.isi = {}
        self.gembok = threading.Lock()

    def ambil(self, kueri, kedalaman, maks_hasil):
        """Salinan hasil yang masih berlaku, atau None jika belum ada, kedaluwarsa, atau jumlahnya kurang dari maks_hasil."""
        if not self.boleh_simpan(kueri):
            return None
        with self.gembok:
            data = self.isi.get(kunci(kueri, kedalaman))
        if not data or time.monotonic() - data["waktu"] > self.masa or data["maks"] < maks_hasil:
            return None
        return [dict(item) for item in data["hasil"][:maks_hasil]]

    def simpan(self, kueri, kedalaman, maks_hasil, hasil):
        """Menyimpan atau mengganti hasil kueri; jika penuh, isi yang paling lama dibuang."""
        if not hasil or not self.boleh_simpan(kueri):
            return
        with self.gembok:
            self.isi.pop(kunci(kueri, kedalaman), None)
            if len(self.isi) >= self.maks_isi:
                self.isi.pop(next(iter(self.isi)))
            self.isi[kunci(kueri, kedalaman)] = {
                "waktu": time.monotonic(),
                "maks": maks_hasil,
                "hasil": [dict(item) for item in hasil],
            }

    def boleh_simpan(self, kueri):
        return self.masa > 0 and self.maks_isi > 0 and not POLA_CEPAT_BASI.search(kueri.lower())


def kunci(kueri, kedalaman):
    """Kueri yang beda huruf besar atau spasinya dianggap sama."""
    return " ".join(kueri.lower().split()), kedalaman