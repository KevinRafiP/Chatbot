import re
from datetime import date, timedelta

from alat.jaringan import CacheSingkat, GalatAlat, ambil_json

# setiap satuan dihitung terhadap satuan dasar kelompoknya (meter, kilogram, meter persegi, liter, m/s, byte, detik, joule, pascal)
SATUAN = {
    "panjang": {"mm": 0.001, "cm": 0.01, "dm": 0.1, "m": 1, "km": 1000, "inci": 0.0254, "in": 0.0254, "inch": 0.0254,
                "kaki": 0.3048, "ft": 0.3048, "feet": 0.3048, "yard": 0.9144, "yd": 0.9144, "mil": 1609.344, "mi": 1609.344,
                "mile": 1609.344, "mil laut": 1852, "nmi": 1852},
    "berat": {"mg": 1e-6, "g": 0.001, "gram": 0.001, "ons": 0.1, "hg": 0.1, "pon": 0.5, "kg": 1, "kuintal": 100,
              "ton": 1000, "lb": 0.45359237, "pound": 0.45359237, "oz": 0.028349523125, "ounce": 0.028349523125},
    "luas": {"mm2": 1e-6, "cm2": 1e-4, "m2": 1, "are": 100, "ha": 10_000, "hektar": 10_000, "km2": 1e6,
             "ft2": 0.09290304, "acre": 4046.8564224, "are tanah": 100},
    "volume": {"ml": 0.001, "cc": 0.001, "l": 1, "liter": 1, "m3": 1000, "sdt": 0.005, "tsp": 0.00492892, "sdm": 0.015,
               "tbsp": 0.0147868, "cup": 0.24, "gelas": 0.24, "floz": 0.0295735, "galon": 3.78541, "gallon": 3.78541},
    "kecepatan": {"m/s": 1, "km/jam": 1 / 3.6, "km/h": 1 / 3.6, "kph": 1 / 3.6, "mph": 0.44704, "knot": 0.514444, "kn": 0.514444},
    "data": {"bit": 0.125, "b": 1, "byte": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024, "mib": 1024 ** 2,
             "gib": 1024 ** 3, "tib": 1024 ** 4},
    "waktu": {"ms": 0.001, "detik": 1, "s": 1, "menit": 60, "jam": 3600, "hari": 86_400, "minggu": 604_800,
              "bulan": 2_629_746, "tahun": 31_556_952},
    "energi": {"j": 1, "kj": 1000, "kal": 4.184, "cal": 4.184, "kkal": 4184, "kcal": 4184, "wh": 3600, "kwh": 3.6e6},
    "tekanan": {"pa": 1, "kpa": 1000, "bar": 100_000, "atm": 101_325, "psi": 6894.757, "mmhg": 133.322},
}
SUHU = {"c": "c", "celsius": "c", "°c": "c", "f": "f", "fahrenheit": "f", "°f": "f", "k": "k", "kelvin": "k",
        "r": "r", "reamur": "r", "réaumur": "r", "°r": "r"}
POLA_MATA_UANG = re.compile(r"^[A-Za-z]{3}$")
SIMBOL_MATA_UANG = {"rp": "IDR", "rupiah": "IDR", "dolar": "USD", "dollar": "USD", "$": "USD", "euro": "EUR", "€": "EUR",
                    "yen": "JPY", "¥": "JPY", "won": "KRW", "ringgit": "MYR", "riyal": "SAR", "pound": "GBP", "£": "GBP",
                    "baht": "THB", "yuan": "CNY", "rupee": "INR", "peso": "PHP"}


def rapikan_satuan(nama):
    nama = " ".join(str(nama or "").lower().split())
    return nama.replace("²", "2").replace("³", "3").replace("^2", "2").replace("^3", "3").replace(" per ", "/")


def konversi_satuan(nilai, dari, ke):
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise GalatAlat("nilai harus angka")
    dari, ke = rapikan_satuan(dari), rapikan_satuan(ke)
    if dari in SUHU and ke in SUHU:
        return {"nilai": nilai, "dari": dari, "ke": ke, "hasil": round(suhu(nilai, SUHU[dari], SUHU[ke]), 6), "kelompok": "suhu"}
    for kelompok, daftar in SATUAN.items():
        if dari in daftar and ke in daftar:
            hasil = nilai * daftar[dari] / daftar[ke]
            catatan = {"ons": "1 ons Indonesia = 100 gram", "pon": "1 pon Indonesia = 500 gram",
                       "bulan": "1 bulan dihitung rata-rata 30,44 hari"}
            keterangan = [catatan[s] for s in (dari, ke) if s in catatan]
            return {"nilai": nilai, "dari": dari, "ke": ke, "hasil": float(f"{hasil:.10g}"), "kelompok": kelompok,
                    **({"catatan": "; ".join(keterangan)} if keterangan else {})}
    contoh = "; ".join(f"{kelompok}: {', '.join(list(daftar)[:6])}" for kelompok, daftar in SATUAN.items())
    raise GalatAlat(f"satuan {dari} ke {ke} tidak dikenali atau beda kelompok. Contoh satuan: suhu: c, f, k, r; {contoh}")


def suhu(nilai, dari, ke):
    celsius = {"c": nilai, "f": (nilai - 32) * 5 / 9, "k": nilai - 273.15, "r": nilai * 5 / 4}[dari]
    return {"c": celsius, "f": celsius * 9 / 5 + 32, "k": celsius + 273.15, "r": celsius * 4 / 5}[ke]


def kode_mata_uang(nama):
    teks = str(nama or "").strip()
    kode = SIMBOL_MATA_UANG.get(teks.lower(), teks.upper())
    if not POLA_MATA_UANG.match(kode):
        raise GalatAlat(f"mata uang '{teks}' tidak dikenali; pakai kode 3 huruf seperti IDR, USD, JPY")
    return kode


class Kurs:
    """Kurs dari Frankfurter (data Bank Sentral Eropa, diperbarui sekali tiap hari kerja) atau ExchangeRate-API open access."""

    def __init__(self, p):
        self.p = p
        self.cache = CacheSingkat(p.kurs_cache_detik, 100)

    def konversi(self, jumlah, dari, ke, riwayat_hari=0):
        try:
            jumlah = float(jumlah if jumlah not in (None, "") else 1)
        except (TypeError, ValueError):
            raise GalatAlat("jumlah harus angka")
        dari = kode_mata_uang(dari)
        tujuan = ke if isinstance(ke, list) else [ke or "IDR"]
        tujuan = [kode_mata_uang(k) for k in tujuan[:8]]
        data = self.cache.ambil_atau_buat(f"terbaru-{dari}", lambda: self.terbaru(dari))
        hasil = []
        for kode in tujuan:
            if kode == dari:
                hasil.append({"ke": kode, "kurs": 1, "hasil": jumlah})
                continue
            kurs = data["kurs"].get(kode)
            if kurs is None:
                hasil.append({"ke": kode, "galat": f"kurs {dari} ke {kode} tidak tersedia di {data['penyedia']}"})
                continue
            hasil.append({"ke": kode, "kurs": kurs, "hasil": round(jumlah * kurs, 4)})
        balasan = {"jumlah": jumlah, "dari": dari, "hasil": hasil, "tanggal_data": data["tanggal"],
                   "penyedia": data["penyedia"], "catatan": "Kurs referensi, bukan kurs jual beli bank atau money changer."}
        riwayat_hari = min(max(int(riwayat_hari or 0), 0), 366)
        if riwayat_hari and self.p.kurs_provider == "frankfurter" and len(tujuan) == 1 and tujuan[0] != dari:
            balasan["riwayat"] = self.riwayat(dari, tujuan[0], riwayat_hari)
        return balasan

    def terbaru(self, dari):
        if self.p.kurs_provider == "exchangerate":
            data = ambil_json(f"{self.p.kurs_url}/latest/{dari}", None, self.p.batas_waktu, self.p.agen_pengguna)
            if data.get("result") != "success":
                raise GalatAlat(f"mata uang {dari} tidak didukung")
            return {"kurs": data.get("rates") or {}, "tanggal": str(data.get("time_last_update_utc", ""))[:16],
                    "penyedia": "ExchangeRate-API (open.er-api.com)"}
        data = ambil_json(f"{self.p.kurs_url}/latest", {"base": dari}, self.p.batas_waktu, self.p.agen_pengguna)
        return {"kurs": data.get("rates") or {}, "tanggal": data.get("date", ""), "penyedia": "Frankfurter (Bank Sentral Eropa)"}

    def riwayat(self, dari, ke, hari):
        """Kurs harian untuk grafik; titik dikurangi agar jawaban tidak terlalu panjang."""
        akhir = date.today()
        awal = akhir - timedelta(days=hari)
        data = self.cache.ambil_atau_buat(f"riwayat-{dari}-{ke}-{hari}-{akhir}", lambda: ambil_json(
            f"{self.p.kurs_url}/{awal.isoformat()}..{akhir.isoformat()}", {"base": dari, "symbols": ke},
            self.p.batas_waktu, self.p.agen_pengguna))
        titik = sorted((tanggal, nilai.get(ke)) for tanggal, nilai in (data.get("rates") or {}).items() if nilai.get(ke))
        langkah = max(1, len(titik) // 30)
        dipilih = titik[::langkah]
        if titik and dipilih[-1] != titik[-1]:
            dipilih.append(titik[-1])
        return [{"tanggal": tanggal, "kurs": nilai} for tanggal, nilai in dipilih]


class AlatKonversi:
    def __init__(self, p):
        self.kurs = Kurs(p) if p.kurs_url else None

    def jalankan(self, argumen):
        jenis = str(argumen.get("jenis", "satuan")).lower()
        if jenis in ("mata_uang", "kurs", "uang"):
            if self.kurs is None:
                raise GalatAlat("konversi mata uang tidak aktif")
            return self.kurs.konversi(argumen.get("nilai"), argumen.get("dari"), argumen.get("ke"), argumen.get("riwayat_hari"))
        return konversi_satuan(argumen.get("nilai"), argumen.get("dari"), argumen.get("ke"))