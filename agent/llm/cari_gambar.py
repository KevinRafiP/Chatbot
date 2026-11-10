import json
import logging
import urllib.parse
import urllib.request
import uuid

from alat.jaringan import unduh_dengan_batas

ALAMAT_SAUCENAO = "https://saucenao.com/search.php"
MAKS_HASIL = 3
MAKS_HURUF_NILAI = 200


def buat_pencari_gambar(cfg):
    """Mengembalikan (pencari, keterangan untuk tabel awal) sesuai CARI_GAMBAR_PENYEDIA; pencari None jika mati atau kunci API kosong."""
    if cfg.cari_gambar_penyedia != "saucenao":
        return None, "mati"
    if not cfg.saucenao_api_key:
        return None, "mati, SAUCENAO_API_KEY kosong"
    pencari = PencariSauceNAO(cfg.saucenao_api_key, cfg.saucenao_ambang, cfg.saucenao_batas_detik)
    return pencari, f"aktif, SauceNAO (kemiripan minimal {cfg.saucenao_ambang}%)"


class PencariSauceNAO:
    """Mencari asal gambar anime, game, atau ilustrasi di SauceNAO. Keputusan cocok atau tidak diambil dari
    angka kemiripan, jadi tidak memakai token model. Gambarnya hanya dikirim, tidak disimpan."""

    def __init__(self, api_key, ambang, batas_waktu):
        self.api_key = api_key
        self.ambang = ambang
        self.batas_waktu = batas_waktu

    def cari(self, isi, jenis):
        """Mengembalikan teks hasil jika ada yang mencapai ambang kemiripan; None jika tidak cocok atau layanan gagal."""
        try:
            data = self.kirim(isi, jenis)
        except Exception as galat:
            logging.warning("SauceNAO gagal, gambar dibaca model: %s", galat)
            return None
        status = (data.get("header") or {}).get("status", 0)
        if status != 0:
            logging.warning("SauceNAO menolak permintaan (status %s), gambar dibaca model", status)
            return None
        cocok = [h for h in data.get("results") or [] if self.layak(h)][:MAKS_HASIL]
        if not cocok:
            logging.info("SauceNAO tidak menemukan yang mirip, gambar dibaca model")
            return None
        return susun_teks(cocok)

    def kirim(self, isi, jenis):
        parameter = {"output_type": 2, "api_key": self.api_key, "numres": MAKS_HASIL * 2, "db": 999, "hide": 3}
        alamat = f"{ALAMAT_SAUCENAO}?{urllib.parse.urlencode(parameter)}"
        batas = uuid.uuid4().hex
        badan = (f'--{batas}\r\nContent-Disposition: form-data; name="file"; filename="gambar.{jenis}"\r\n'
                 f"Content-Type: image/{jenis}\r\n\r\n").encode("ascii") + isi + f"\r\n--{batas}--\r\n".encode("ascii")
        permintaan = urllib.request.Request(alamat, data=badan, method="POST", headers={
            "User-Agent": "Vokapas/1.0", "Accept": "application/json", "Content-Type": f"multipart/form-data; boundary={batas}"})
        return json.loads(unduh_dengan_batas(permintaan, self.batas_waktu))

    def layak(self, hasil):
        kepala = hasil.get("header") or {}
        try:
            kemiripan = float(kepala.get("similarity", 0))
        except (TypeError, ValueError):
            return False
        # hidden bukan 0 berarti SauceNAO menandai gambar sumbernya tidak aman
        return kemiripan >= self.ambang and not kepala.get("hidden") and bool(hasil.get("data"))


def rapikan(nilai):
    if isinstance(nilai, list):
        nilai = ", ".join(str(n) for n in nilai if n)
    return " ".join(str(nilai or "").split())[:MAKS_HURUF_NILAI]


def susun_teks(daftar_hasil):
    baris = ["[Hasil pencarian asal gambar (SauceNAO), bukan isi gambar. Gambar ini kemungkinan besar berasal dari:]"]
    for nomor, hasil in enumerate(daftar_hasil, 1):
        data, kepala = hasil["data"], hasil["header"]
        rincian = {
            "Judul": rapikan(data.get("title") or data.get("eng_name") or data.get("jp_name")),
            "Karakter": rapikan(data.get("characters")),
            "Karya atau seri": rapikan(data.get("material") or data.get("source")),
            "Pembuat": rapikan(data.get("creator") or data.get("member_name") or data.get("author_name")),
            "Link": rapikan((data.get("ext_urls") or [""])[0]),
        }
        isi = "; ".join(f"{nama}: {nilai}" for nama, nilai in rincian.items() if nilai)
        baris.append(f"{nomor}. {isi or 'tanpa keterangan'} (kemiripan {rapikan(kepala.get('similarity'))}%)")
    baris.append("Pakai nama di atas sebagai kata kunci jika perlu mencari keterangan lebih lanjut.")
    return "\n".join(baris)
