from alat.jaringan import GalatAlat, ambil_json


class AlatPengetahuan:
    """Mencari ulang data pengetahuan di backend dengan kata kunci lain, karena pencarian awal hanya memakai kalimat pertanyaan."""

    def __init__(self, p):
        self.p = p

    def jalankan(self, argumen, catatan):
        kueri = " ".join(str(argumen.get("kueri") or "").split())[:300]
        if not kueri:
            raise GalatAlat("kueri wajib diisi")
        data = ambil_json(f"{self.p.backend_url}/internal/pengetahuan/cari", None, self.p.batas_waktu, self.p.agen_pengguna,
                          metode="POST", badan={"kueri": kueri}, header={"X-API-Key": self.p.backend_api_key})
        daftar = data.get("data") or []
        hasil = []
        for item in daftar[:5]:
            judul, isi = str(item.get("judul", "")), str(item.get("isi", ""))
            hasil.append({"nomor": tambah_internal(catatan, judul, isi), "judul": judul, "isi": isi[:3000]})
        return {"hasil": hasil, "catatan": "Data pengetahuan; jangan menyebut asalnya di jawaban. Kosong berarti tidak ada data yang cocok."}


def tambah_internal(catatan, judul, isi):
    """Data pengetahuan tidak punya URL, jadi dicatat berdasarkan judulnya agar nomor sitasinya tidak tertukar."""
    for i, sumber in enumerate(catatan["sumber"], start=1):
        if not sumber["url"] and sumber["judul"] == judul:
            return i
    catatan["sumber"].append({"judul": judul, "url": ""})
    nomor = len(catatan["sumber"])
    catatan["bukti"][nomor] = {"tingkat": "internal", "isi": isi[:3000]}
    return nomor