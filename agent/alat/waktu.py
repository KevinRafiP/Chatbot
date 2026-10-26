import calendar
import re
from datetime import date, datetime, timedelta, timezone

from alat.jaringan import CacheSingkat, GalatAlat, ambil_json
from alat.tempat import cari_tempat

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # Python lama tanpa zoneinfo
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

# nama yang sering dipakai pengguna; nama lain dicari lewat geokode (zona waktu kota diambil dari sana)
ZONA_DIKENAL = {
    "wib": "Asia/Jakarta", "wita": "Asia/Makassar", "wit": "Asia/Jayapura", "utc": "UTC", "gmt": "UTC",
    "indonesia": "Asia/Jakarta", "jakarta": "Asia/Jakarta", "bandung": "Asia/Jakarta", "surabaya": "Asia/Jakarta",
    "semarang": "Asia/Jakarta", "yogyakarta": "Asia/Jakarta", "jogja": "Asia/Jakarta", "medan": "Asia/Jakarta",
    "palembang": "Asia/Jakarta", "pontianak": "Asia/Pontianak", "bali": "Asia/Makassar", "denpasar": "Asia/Makassar",
    "makassar": "Asia/Makassar", "balikpapan": "Asia/Makassar", "manado": "Asia/Makassar", "mataram": "Asia/Makassar",
    "jayapura": "Asia/Jayapura", "ambon": "Asia/Jayapura", "papua": "Asia/Jayapura",
    "singapura": "Asia/Singapore", "singapore": "Asia/Singapore", "kuala lumpur": "Asia/Kuala_Lumpur", "malaysia": "Asia/Kuala_Lumpur",
    "bangkok": "Asia/Bangkok", "manila": "Asia/Manila", "tokyo": "Asia/Tokyo", "jepang": "Asia/Tokyo", "seoul": "Asia/Seoul",
    "korea": "Asia/Seoul", "beijing": "Asia/Shanghai", "china": "Asia/Shanghai", "tiongkok": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong", "taipei": "Asia/Taipei", "india": "Asia/Kolkata", "dubai": "Asia/Dubai",
    "riyadh": "Asia/Riyadh", "mekkah": "Asia/Riyadh", "makkah": "Asia/Riyadh", "madinah": "Asia/Riyadh",
    "london": "Europe/London", "inggris": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "amsterdam": "Europe/Amsterdam", "belanda": "Europe/Amsterdam", "moskow": "Europe/Moscow", "istanbul": "Europe/Istanbul",
    "new york": "America/New_York", "los angeles": "America/Los_Angeles", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne", "perth": "Australia/Perth", "auckland": "Pacific/Auckland",
}
POLA_SELISIH_UTC = re.compile(r"^(?:utc|gmt)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$")
FORMAT_TANGGAL = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M", "%d-%m-%Y",
                  "%d/%m/%Y %H:%M", "%d/%m/%Y")
SATUAN_TAMBAH = {"hari": "hari", "day": "hari", "days": "hari", "minggu": "minggu", "pekan": "minggu", "week": "minggu",
                 "weeks": "minggu", "bulan": "bulan", "month": "bulan", "months": "bulan", "tahun": "tahun", "year": "tahun",
                 "years": "tahun", "jam": "jam", "hour": "jam", "hours": "jam", "menit": "menit", "minute": "menit"}

cache_libur = CacheSingkat(24 * 3600, 50)
# "hari ini" mengikuti WIB, bukan jam server (Render memakai UTC)
WIB = timezone(timedelta(hours=7), "WIB")


class AlatWaktu:
    def __init__(self, p):
        self.p = p

    def jalankan(self, argumen):
        aksi = str(argumen.get("aksi", "sekarang")).lower()
        if aksi == "sekarang":
            daftar = argumen.get("lokasi") or ["WIB"]
            daftar = daftar if isinstance(daftar, list) else [daftar]
            return {"waktu": [self.waktu_di(nama) for nama in daftar[:8]]}
        if aksi == "konversi":
            return self.konversi(argumen)
        if aksi == "selisih":
            return selisih(baca_tanggal(argumen.get("dari")).date(), baca_tanggal(argumen.get("sampai") or "hari ini").date())
        if aksi == "tambah":
            return tambah(baca_tanggal(argumen.get("tanggal") or "hari ini"), argumen.get("jumlah", 0), argumen.get("satuan", "hari"))
        if aksi == "info":
            return info_tanggal(baca_tanggal(argumen.get("tanggal") or "hari ini").date())
        if aksi == "umur":
            return umur(baca_tanggal(argumen.get("tanggal")).date(), baca_tanggal(argumen.get("sampai") or "hari ini").date())
        if aksi == "libur":
            return self.libur(argumen.get("tahun"), argumen.get("negara", "ID"), argumen.get("bulan"))
        raise GalatAlat("aksi harus salah satu dari: sekarang, konversi, selisih, tambah, info, umur, libur")

    def zona(self, nama):
        """Mengubah nama zona, singkatan (WIB), UTC+7, nama zona IANA, atau nama kota menjadi zona waktu."""
        teks = " ".join(str(nama or "").split())
        kecil = teks.lower()
        cocok = POLA_SELISIH_UTC.match(kecil)
        if cocok:
            jam, menit = int(cocok.group(2)), int(cocok.group(3) or 0)
            if jam > 14 or menit >= 60:
                raise GalatAlat(f"selisih UTC {teks} tidak valid")
            arah = 1 if cocok.group(1) == "+" else -1
            return timezone(arah * timedelta(hours=jam, minutes=menit), teks.upper()), teks.upper()
        nama_iana = ZONA_DIKENAL.get(kecil) or (teks if "/" in teks else "")
        label = teks
        if not nama_iana:
            tempat = cari_tempat(teks, self.p)
            nama_iana = tempat["zona"]
            label = ", ".join(bagian for bagian in (tempat["nama"], tempat["negara"]) if bagian)
        return buka_zona(nama_iana), label

    def waktu_di(self, nama):
        zona, label = self.zona(nama)
        sekarang = datetime.now(timezone.utc).astimezone(zona)
        return {"lokasi": label, **uraikan(sekarang)}

    def konversi(self, argumen):
        zona_asal, label_asal = self.zona(argumen.get("dari") or "WIB")
        waktu = baca_tanggal(argumen.get("waktu") or "sekarang", zona_asal)
        if waktu.tzinfo is None:
            waktu = waktu.replace(tzinfo=zona_asal)
        tujuan = argumen.get("ke") or ["UTC"]
        tujuan = tujuan if isinstance(tujuan, list) else [tujuan]
        hasil = []
        for nama in tujuan[:8]:
            zona, label = self.zona(nama)
            hasil.append({"lokasi": label, **uraikan(waktu.astimezone(zona))})
        return {"asal": {"lokasi": label_asal, **uraikan(waktu)}, "hasil": hasil}

    def libur(self, tahun, negara, bulan=None):
        if not self.p.libur_url:
            raise GalatAlat("data hari libur tidak aktif")
        tahun = int(tahun or hari_ini().year)
        negara = str(negara or "ID").upper()[:2]
        if not 1990 <= tahun <= 2100 or not negara.isalpha():
            raise GalatAlat("tahun atau kode negara tidak valid")
        data = cache_libur.ambil_atau_buat(f"{tahun}-{negara}", lambda: ambil_json(
            f"{self.p.libur_url}/PublicHolidays/{tahun}/{negara}", None, self.p.batas_waktu, self.p.agen_pengguna))
        daftar = []
        for item in data or []:
            hari = date.fromisoformat(item["date"])
            if bulan and hari.month != int(bulan):
                continue
            daftar.append({"tanggal": item["date"], "hari": HARI[hari.weekday()], "nama": item.get("localName") or item.get("name"),
                           "nama_inggris": item.get("name")})
        return {"negara": negara, "tahun": tahun, "libur": daftar,
                "catatan": "Data dari Nager.Date; cuti bersama dan libur daerah bisa tidak tercantum."}


def hari_ini():
    return datetime.now(WIB).date()


def buka_zona(nama_iana):
    if ZoneInfo is None:
        raise GalatAlat("zona waktu tidak didukung di server ini")
    try:
        return ZoneInfo(nama_iana)
    except (ZoneInfoNotFoundError, ValueError):
        raise GalatAlat(f"zona waktu {nama_iana} tidak dikenal (pasang paket tzdata jika di Windows)")


def baca_tanggal(teks, zona=None):
    """Membaca tanggal atau jam; "sekarang", "hari ini", "besok", dan "kemarin" juga dikenali."""
    teks = " ".join(str(teks or "").split()).lower()
    sekarang = datetime.now(zona or WIB)
    kata = {"sekarang": 0, "now": 0, "hari ini": 0, "today": 0, "besok": 1, "tomorrow": 1, "kemarin": -1, "yesterday": -1, "lusa": 2}
    if teks in kata:
        hasil = sekarang + timedelta(days=kata[teks])
        return hasil if teks in ("sekarang", "now") else hasil.replace(hour=0, minute=0, second=0, microsecond=0)
    jam = re.fullmatch(r"(\d{1,2})[:.](\d{2})", teks)
    if jam:
        return sekarang.replace(hour=int(jam.group(1)), minute=int(jam.group(2)), second=0, microsecond=0)
    for pola in FORMAT_TANGGAL:
        try:
            return datetime.strptime(teks, pola)
        except ValueError:
            continue
    raise GalatAlat(f"tanggal '{teks}' tidak dikenali; pakai format YYYY-MM-DD atau YYYY-MM-DD HH:MM")


def uraikan(waktu):
    hasil = {
        "tanggal": waktu.strftime("%Y-%m-%d"),
        "jam": waktu.strftime("%H:%M"),
        "hari": HARI[waktu.weekday()],
        "teks": f"{HARI[waktu.weekday()]}, {waktu.day} {BULAN[waktu.month - 1]} {waktu.year} pukul {waktu:%H.%M}",
    }
    # tanggal tanpa zona (misalnya hasil tambah hari) tidak diberi keterangan UTC
    if waktu.tzinfo is not None:
        menit = int((waktu.utcoffset() or timedelta()).total_seconds() // 60)
        tanda = "+" if menit >= 0 else "-"
        hasil["utc"] = f"UTC{tanda}{abs(menit) // 60}" + (f":{abs(menit) % 60:02d}" if menit % 60 else "")
        hasil["singkatan"] = waktu.tzname() or ""
    return hasil


def selisih(dari, sampai):
    awal, akhir = sorted((dari, sampai))
    tahun, bulan, hari = beda_kalender(awal, akhir)
    total = (akhir - awal).days
    hari_kerja = sum(1 for i in range(total) if (awal + timedelta(days=i)).weekday() < 5) if total <= 40_000 else None
    return {"dari": dari.isoformat(), "sampai": sampai.isoformat(), "total_hari": total, "total_minggu": round(total / 7, 2),
            "rincian": f"{tahun} tahun {bulan} bulan {hari} hari", "hari_kerja_senin_jumat": hari_kerja,
            "arah": "maju" if sampai >= dari else "mundur"}


def beda_kalender(awal, akhir):
    bulan = (akhir.year - awal.year) * 12 + akhir.month - awal.month
    if akhir.day < awal.day:
        bulan -= 1
    titik = tambah_bulan(awal, bulan)
    return bulan // 12, bulan % 12, (akhir - titik).days


def tambah_bulan(tanggal, jumlah):
    bulan = tanggal.month - 1 + jumlah
    tahun = tanggal.year + bulan // 12
    bulan = bulan % 12 + 1
    return tanggal.replace(year=tahun, month=bulan, day=min(tanggal.day, calendar.monthrange(tahun, bulan)[1]))


def tambah(tanggal, jumlah, satuan):
    try:
        jumlah = int(float(jumlah))
    except (TypeError, ValueError):
        raise GalatAlat("jumlah harus angka")
    if abs(jumlah) > 100_000:
        raise GalatAlat("jumlah terlalu besar")
    satuan = SATUAN_TAMBAH.get(str(satuan).lower())
    if satuan == "hari":
        hasil = tanggal + timedelta(days=jumlah)
    elif satuan == "minggu":
        hasil = tanggal + timedelta(weeks=jumlah)
    elif satuan == "bulan":
        hasil = tambah_bulan(tanggal, jumlah)
    elif satuan == "tahun":
        hasil = tambah_bulan(tanggal, jumlah * 12)
    elif satuan == "jam":
        hasil = tanggal + timedelta(hours=jumlah)
    elif satuan == "menit":
        hasil = tanggal + timedelta(minutes=jumlah)
    else:
        raise GalatAlat("satuan harus hari, minggu, bulan, tahun, jam, atau menit")
    return {"dari": tanggal.strftime("%Y-%m-%d %H:%M"), "hasil": uraikan(hasil)}


def info_tanggal(tanggal):
    awal_tahun = date(tanggal.year, 1, 1)
    return {
        "tanggal": tanggal.isoformat(),
        "hari": HARI[tanggal.weekday()],
        "teks": f"{HARI[tanggal.weekday()]}, {tanggal.day} {BULAN[tanggal.month - 1]} {tanggal.year}",
        "hari_ke": (tanggal - awal_tahun).days + 1,
        "minggu_ke_iso": tanggal.isocalendar()[1],
        "tahun_kabisat": calendar.isleap(tanggal.year),
        "jumlah_hari_bulan_ini": calendar.monthrange(tanggal.year, tanggal.month)[1],
        "selisih_dari_hari_ini": (tanggal - hari_ini()).days,
    }


def umur(lahir, pada):
    if lahir > pada:
        raise GalatAlat("tanggal lahir setelah tanggal acuan")
    tahun, bulan, hari = beda_kalender(lahir, pada)
    ulang_tahun = tambah_bulan(lahir, (pada.year - lahir.year) * 12)
    if ulang_tahun < pada:
        ulang_tahun = tambah_bulan(lahir, (pada.year - lahir.year + 1) * 12)
    return {"tanggal_lahir": lahir.isoformat(), "hari_lahir": HARI[lahir.weekday()], "umur": f"{tahun} tahun {bulan} bulan {hari} hari",
            "umur_tahun": tahun, "total_hari": (pada - lahir).days, "ulang_tahun_berikutnya": ulang_tahun.isoformat(),
            "hari_menuju_ulang_tahun": (ulang_tahun - pada).days}