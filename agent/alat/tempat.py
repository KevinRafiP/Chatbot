from alat.jaringan import CacheSingkat, GalatAlat, ambil_json

# nama tempat jarang berubah koordinatnya, jadi hasil geokode disimpan sehari
cache_tempat = CacheSingkat(24 * 3600, 500)


def cari_tempat(nama, p):
    """Mengubah nama kota atau tempat menjadi koordinat dan zona waktu lewat geokode Open-Meteo."""
    nama = " ".join(str(nama or "").split())[:100]
    if not nama:
        raise GalatAlat("nama tempat wajib diisi")
    if not p.geokode_url:
        raise GalatAlat("pencarian tempat tidak aktif")

    def buat():
        # "Bandung, Jawa Barat" dicari dengan bagian pertama, bagian berikutnya dipakai untuk memilih hasil
        utama, _, petunjuk = nama.partition(",")
        data = ambil_json(f"{p.geokode_url}/search", {"name": utama.strip(), "count": 5, "language": "id", "format": "json"},
                          p.batas_waktu, p.agen_pengguna)
        hasil = data.get("results") or []
        if not hasil:
            raise GalatAlat(f"tempat {nama} tidak ditemukan")
        petunjuk = petunjuk.strip().lower()
        pilihan = next((h for h in hasil if petunjuk and petunjuk in f"{h.get('admin1', '')} {h.get('country', '')}".lower()), hasil[0])
        return {
            "nama": pilihan.get("name", utama),
            "provinsi": pilihan.get("admin1", ""),
            "negara": pilihan.get("country", ""),
            "kode_negara": pilihan.get("country_code", ""),
            "lintang": pilihan.get("latitude"),
            "bujur": pilihan.get("longitude"),
            "zona": pilihan.get("timezone", ""),
        }

    return dict(cache_tempat.ambil_atau_buat(nama.lower(), buat))