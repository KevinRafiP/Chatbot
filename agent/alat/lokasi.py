import math
from datetime import datetime

from alat.jaringan import CacheSingkat, GalatAlat, ambil_json
from alat.tempat import cari_tempat
from alat.waktu import WIB

# kode cuaca WMO yang dipakai Open-Meteo
KODE_CUACA = {
    0: "cerah", 1: "cerah berawan", 2: "berawan sebagian", 3: "mendung", 45: "berkabut", 48: "kabut beku",
    51: "gerimis ringan", 53: "gerimis", 55: "gerimis lebat", 61: "hujan ringan", 63: "hujan sedang", 65: "hujan lebat",
    66: "hujan beku ringan", 67: "hujan beku lebat", 71: "salju ringan", 73: "salju", 75: "salju lebat", 77: "butiran salju",
    80: "hujan lokal ringan", 81: "hujan lokal", 82: "hujan lokal sangat lebat", 95: "badai petir",
    96: "badai petir dengan hujan es", 99: "badai petir dengan hujan es lebat",
}
NAMA_SALAT = {"Imsak": "imsak", "Fajr": "subuh", "Sunrise": "terbit", "Dhuhr": "zuhur", "Asr": "asar", "Maghrib": "magrib", "Isha": "isya"}
JENIS_GEMPA = {"terbaru": "autogempa.json", "terkini": "gempaterkini.json", "dirasakan": "gempadirasakan.json"}
JARI_JARI_BUMI_KM = 6371.0088

cache_gempa = CacheSingkat(60, 10)
cache_wilayah = CacheSingkat(7 * 24 * 3600, 300)


class AlatLokasi:
    def __init__(self, p):
        self.p = p

    def jalankan(self, argumen, catatan, tambah_sumber):
        jenis = str(argumen.get("jenis", "")).lower()
        if jenis == "cuaca":
            return self.cuaca(argumen.get("tempat"), argumen.get("hari"), catatan, tambah_sumber)
        if jenis == "salat":
            return self.salat(argumen.get("tempat"), argumen.get("tanggal"), catatan, tambah_sumber)
        if jenis == "gempa":
            return self.gempa(argumen.get("daftar", "terbaru"), catatan, tambah_sumber)
        if jenis == "jarak":
            return self.jarak(argumen.get("dari"), argumen.get("ke"))
        if jenis == "wilayah":
            return self.wilayah(argumen.get("provinsi"), argumen.get("kota"), argumen.get("kecamatan"))
        if jenis == "koordinat":
            return cari_tempat(argumen.get("tempat"), self.p)
        raise GalatAlat("jenis harus cuaca, salat, gempa, jarak, wilayah, atau koordinat")

    def cuaca(self, nama, hari, catatan, tambah_sumber):
        if not self.p.cuaca_url:
            raise GalatAlat("prakiraan cuaca tidak aktif")
        tempat = cari_tempat(nama, self.p)
        hari = min(max(int(hari or 3), 1), 7)
        data = ambil_json(f"{self.p.cuaca_url}/forecast", {
            "latitude": tempat["lintang"], "longitude": tempat["bujur"], "timezone": "auto", "forecast_days": hari,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        }, self.p.batas_waktu, self.p.agen_pengguna)
        sekarang = data.get("current") or {}
        harian = data.get("daily") or {}
        daftar = []
        for i, tanggal in enumerate(harian.get("time") or []):
            daftar.append({
                "tanggal": tanggal,
                "cuaca": KODE_CUACA.get(nilai(harian, "weather_code", i), "tidak diketahui"),
                "suhu_min_c": nilai(harian, "temperature_2m_min", i),
                "suhu_maks_c": nilai(harian, "temperature_2m_max", i),
                "peluang_hujan_persen": nilai(harian, "precipitation_probability_max", i),
                "curah_hujan_mm": nilai(harian, "precipitation_sum", i),
            })
        nomor = tambah_sumber(catatan, f"Prakiraan cuaca {tempat['nama']} - Open-Meteo", "https://open-meteo.com/", "")
        return {"tempat": tempat, "sekarang": {
            "waktu": sekarang.get("time"), "suhu_c": sekarang.get("temperature_2m"), "terasa_c": sekarang.get("apparent_temperature"),
            "kelembapan_persen": sekarang.get("relative_humidity_2m"), "angin_kmj": sekarang.get("wind_speed_10m"),
            "cuaca": KODE_CUACA.get(sekarang.get("weather_code"), "tidak diketahui"),
        }, "harian": daftar, "nomor": nomor, "catatan": "Prakiraan model cuaca; untuk peringatan dini resmi lihat BMKG."}

    def salat(self, nama, tanggal, catatan, tambah_sumber):
        if not self.p.salat_url:
            raise GalatAlat("jadwal salat tidak aktif")
        tempat = cari_tempat(nama, self.p)
        hari = tanggal_dmy(tanggal)
        data = ambil_json(f"{self.p.salat_url}/timings/{hari}", {
            "latitude": tempat["lintang"], "longitude": tempat["bujur"], "method": self.p.salat_metode,
            "timezonestring": tempat["zona"] or "Asia/Jakarta",
        }, self.p.batas_waktu, self.p.agen_pengguna)
        isi = data.get("data") or {}
        jadwal = {NAMA_SALAT[k]: str(v)[:5] for k, v in (isi.get("timings") or {}).items() if k in NAMA_SALAT}
        hijriah = (isi.get("date") or {}).get("hijri") or {}
        metode = ((isi.get("meta") or {}).get("method") or {}).get("name", "")
        nomor = tambah_sumber(catatan, f"Jadwal salat {tempat['nama']} - Aladhan", "https://aladhan.com/", "")
        return {"tempat": tempat, "tanggal": hari, "jadwal": jadwal, "metode": metode,
                "hijriah": f"{hijriah.get('day', '')} {(hijriah.get('month') or {}).get('en', '')} {hijriah.get('year', '')}".strip(),
                "nomor": nomor, "catatan": "Hasil hitungan astronomis; bisa selisih beberapa menit dari jadwal masjid setempat."}

    def gempa(self, daftar, catatan, tambah_sumber):
        if not self.p.gempa_url:
            raise GalatAlat("info gempa tidak aktif")
        berkas = JENIS_GEMPA.get(str(daftar).lower(), JENIS_GEMPA["terbaru"])
        data = cache_gempa.ambil_atau_buat(berkas, lambda: ambil_json(f"{self.p.gempa_url}/{berkas}", None,
                                                                        self.p.batas_waktu, self.p.agen_pengguna))
        isi = (data.get("Infogempa") or {}).get("gempa") or []
        isi = isi if isinstance(isi, list) else [isi]
        hasil = [{
            "waktu": f"{g.get('Tanggal', '')} {g.get('Jam', '')}".strip(), "magnitudo": g.get("Magnitude"),
            "kedalaman": g.get("Kedalaman"), "lokasi": g.get("Wilayah"), "koordinat": f"{g.get('Lintang', '')} {g.get('Bujur', '')}".strip(),
            "potensi": g.get("Potensi"), "dirasakan": g.get("Dirasakan"),
        } for g in isi[:10]]
        nomor = tambah_sumber(catatan, "Info gempa BMKG", "https://www.bmkg.go.id/gempabumi", "")
        return {"gempa": hasil, "nomor": nomor, "catatan": "Sumber data: BMKG."}

    def jarak(self, dari, ke):
        asal, tujuan = cari_tempat(dari, self.p), cari_tempat(ke, self.p)
        lurus = garis_lurus(asal["lintang"], asal["bujur"], tujuan["lintang"], tujuan["bujur"])
        hasil = {"dari": asal, "ke": tujuan, "garis_lurus_km": round(lurus, 1)}
        if self.p.rute_url:
            try:
                rute = ambil_json(f"{self.p.rute_url}/route/v1/driving/{asal['bujur']},{asal['lintang']};{tujuan['bujur']},{tujuan['lintang']}",
                                  {"overview": "false"}, self.p.batas_waktu, self.p.agen_pengguna)
                jalan = (rute.get("routes") or [{}])[0]
                if jalan.get("distance") is not None:
                    hasil["jalan_darat_km"] = round(jalan["distance"] / 1000, 1)
                    hasil["perkiraan_waktu_mobil"] = durasi(jalan.get("duration", 0))
            except Exception:
                hasil["catatan_rute"] = "rute jalan darat tidak ditemukan (mungkin terpisah laut)"
        hasil["catatan"] = "Waktu tempuh perkiraan tanpa macet; jarak dihitung dari titik pusat kota."
        return hasil

    def wilayah(self, provinsi=None, kota=None, kecamatan=None):
        """Daftar wilayah administrasi Indonesia: provinsi, lalu kabupaten/kota, kecamatan, dan kelurahan/desa."""
        if not self.p.wilayah_url:
            raise GalatAlat("data wilayah tidak aktif")
        daftar = self.ambil_wilayah("provinces.json")
        jalur = []
        for nama, berkas in ((provinsi, "regencies/{}.json"), (kota, "districts/{}.json"), (kecamatan, "villages/{}.json")):
            if not nama:
                break
            pilihan = cocokkan(daftar, nama)
            jalur.append(pilihan["name"])
            daftar = self.ambil_wilayah(berkas.format(pilihan["code"]))
        tingkat = ["provinsi", "kabupaten/kota", "kecamatan", "kelurahan/desa"][len(jalur)]
        return {"induk": " > ".join(jalur) or "Indonesia", "tingkat": tingkat, "jumlah": len(daftar),
                "daftar": [w["name"] for w in daftar][:200], "sumber": "wilayah.id (Kepmendagri)"}

    def ambil_wilayah(self, berkas):
        data = cache_wilayah.ambil_atau_buat(berkas, lambda: ambil_json(f"{self.p.wilayah_url}/{berkas}", None,
                                                                          self.p.batas_waktu, self.p.agen_pengguna))
        return data.get("data") or []


def nilai(harian, kunci, i):
    daftar = harian.get(kunci) or []
    return daftar[i] if i < len(daftar) else None


def tanggal_dmy(teks):
    if not teks or str(teks).lower() in ("hari ini", "sekarang", "today"):
        return datetime.now(WIB).strftime("%d-%m-%Y")
    try:
        return datetime.strptime(str(teks), "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        raise GalatAlat("tanggal harus berformat YYYY-MM-DD")


def garis_lurus(lintang1, bujur1, lintang2, bujur2):
    p1, p2 = math.radians(lintang1), math.radians(lintang2)
    dp, dl = p2 - p1, math.radians(bujur2 - bujur1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * JARI_JARI_BUMI_KM * math.asin(math.sqrt(a))


def durasi(detik):
    menit = round(detik / 60)
    return f"{menit // 60} jam {menit % 60} menit" if menit >= 60 else f"{menit} menit"


def cocokkan(daftar, nama):
    """Mencocokkan nama wilayah tanpa peduli awalan seperti "Kota", "Kabupaten", atau "Provinsi"."""
    def bersih(teks):
        teks = " ".join(str(teks).lower().replace("kab.", "kabupaten").split())
        for awalan in ("provinsi ", "kabupaten ", "kota ", "kecamatan ", "kelurahan ", "desa "):
            teks = teks.removeprefix(awalan)
        return teks

    dicari = bersih(nama)
    tepat = [w for w in daftar if bersih(w["name"]) == dicari]
    # "Kota Bandung" dan "Kabupaten Bandung" sama-sama ada, jadi awalan dari pengguna dipakai untuk memilih
    if len(tepat) > 1:
        awalan = str(nama).lower().split()[0]
        tepat = [w for w in tepat if w["name"].lower().startswith(awalan)] or tepat
    pilihan = tepat or [w for w in daftar if dicari in bersih(w["name"])]
    if not pilihan:
        raise GalatAlat(f"wilayah {nama} tidak ditemukan")
    return pilihan[0]