from alat.jaringan import CacheSingkat, GalatAlat, ambil_json

# nama tempat jarang berubah koordinatnya, jadi hasil geokode disimpan sehari
cache_tempat = CacheSingkat(24 * 3600, 500)
# tanpa petunjuk provinsi atau negara, tempat di Indonesia diutamakan jika cukup besar (ibu kota atau berpenduduk banyak)
# dan tidak jauh lebih kecil dari hasil pertama, jadi "Batu" menjadi Kota Batu tetapi "Paris" tetap Paris di Prancis
KODE_TEMPAT_UTAMA = ("PPLC", "PPLA", "PPLA2", "PPLA3")
MIN_PENDUDUK_UTAMA = 50_000
KALI_PENDUDUK_ASING = 10


def pilih_hasil(hasil, petunjuk):
    if petunjuk:
        return next((h for h in hasil if petunjuk in f"{h.get('admin1', '')} {h.get('country', '')}".lower()), hasil[0])
    pertama = hasil[0]
    if pertama.get("country_code") == "ID":
        return pertama
    lokal = next((h for h in hasil if h.get("country_code") == "ID" and (
        h.get("feature_code") in KODE_TEMPAT_UTAMA or (h.get("population") or 0) >= MIN_PENDUDUK_UTAMA)), None)
    if lokal and (lokal.get("population") or 0) * KALI_PENDUDUK_ASING >= (pertama.get("population") or 0):
        return lokal
    return pertama


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
        pilihan = pilih_hasil(hasil, petunjuk)
        sama = [f"{h.get('name', '')}, {h.get('admin1', '')}, {h.get('country', '')}".strip(", ") for h in hasil
                if h is not pilihan and h.get("name") == pilihan.get("name")]
        return {
            "nama": pilihan.get("name", utama),
            "provinsi": pilihan.get("admin1", ""),
            "negara": pilihan.get("country", ""),
            "kode_negara": pilihan.get("country_code", ""),
            "lintang": pilihan.get("latitude"),
            "bujur": pilihan.get("longitude"),
            "zona": pilihan.get("timezone", ""),
            **({"tempat_lain_bernama_sama": sama[:3]} if sama else {}),
        }

    return dict(cache_tempat.ambil_atau_buat(nama.lower(), buat))