import math

from alat.jaringan import GalatAlat

# UU HPP (UU 7/2021): lapisan penghasilan kena pajak setahun dan tarifnya
LAPISAN_PPH = [(60_000_000, 0.05), (250_000_000, 0.15), (500_000_000, 0.25), (5_000_000_000, 0.30), (math.inf, 0.35)]
PTKP_DIRI = 54_000_000
PTKP_KAWIN = 4_500_000
PTKP_TANGGUNGAN = 4_500_000
BIAYA_JABATAN_MAKS = 6_000_000
NISAB_GRAM_EMAS = 85
KADAR_ZAKAT = 0.025
BERAS_FITRAH_KG = 2.5
MAKS_BULAN = 600


def angka(argumen, nama, bawaan=None, minimal=0.0):
    nilai = argumen.get(nama, bawaan)
    if nilai in (None, ""):
        if bawaan is None:
            raise GalatAlat(f"{nama} wajib diisi")
        nilai = bawaan
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise GalatAlat(f"{nama} harus angka")
    if nilai < minimal or not math.isfinite(nilai):
        raise GalatAlat(f"{nama} tidak boleh kurang dari {minimal:g}")
    return nilai


def rupiah(nilai):
    return round(nilai)


def cicilan(argumen):
    pokok = angka(argumen, "pokok", minimal=1)
    bunga = angka(argumen, "bunga_tahunan_persen", 0)
    bulan = int(angka(argumen, "tenor_bulan", minimal=1))
    if bulan > MAKS_BULAN:
        raise GalatAlat(f"tenor paling lama {MAKS_BULAN} bulan")
    metode = str(argumen.get("metode", "anuitas")).lower()
    r = bunga / 100 / 12
    if metode == "flat":
        angsuran = pokok / bulan + pokok * bunga / 100 / 12
    elif r == 0:
        angsuran = pokok / bulan
    else:
        angsuran = pokok * r / (1 - (1 + r) ** -bulan)

    sisa = pokok
    per_tahun = []
    for ke in range(1, bulan + 1):
        bunga_bulan = pokok * bunga / 100 / 12 if metode == "flat" else sisa * r
        sisa = max(sisa - (angsuran - bunga_bulan), 0)
        if ke % 12 == 0 or ke == bulan:
            per_tahun.append({"bulan_ke": ke, "sisa_pokok": rupiah(sisa)})
    total = angsuran * bulan
    return {"metode": "flat" if metode == "flat" else "anuitas", "cicilan_per_bulan": rupiah(angsuran), "total_bayar": rupiah(total),
            "total_bunga": rupiah(total - pokok), "sisa_pokok_per_tahun": per_tahun[:50],
            "catatan": "Perkiraan; bank bisa menambah biaya provisi, asuransi, atau memakai bunga mengambang."}


def bunga_majemuk(argumen):
    modal = angka(argumen, "modal", 0)
    bunga = angka(argumen, "bunga_tahunan_persen", minimal=0) / 100
    tahun = angka(argumen, "tahun", minimal=0)
    setoran = angka(argumen, "setoran_bulanan", 0)
    kali = int(angka(argumen, "kali_per_tahun", 12, minimal=1))
    if tahun > 100:
        raise GalatAlat("paling lama 100 tahun")
    per_tahun = []
    nilai = modal
    disetor = modal
    bulan_total = int(round(tahun * 12))
    bunga_bulanan = (1 + bunga / kali) ** (kali / 12) - 1
    for bulan in range(1, bulan_total + 1):
        nilai = nilai * (1 + bunga_bulanan) + setoran
        disetor += setoran
        if bulan % 12 == 0 or bulan == bulan_total:
            per_tahun.append({"tahun_ke": round(bulan / 12, 2), "nilai": rupiah(nilai), "total_setoran": rupiah(disetor)})
    return {"nilai_akhir": rupiah(nilai), "total_setoran": rupiah(disetor), "total_bunga": rupiah(nilai - disetor),
            "per_tahun": per_tahun[:100], "catatan": "Setoran dianggap masuk di akhir setiap bulan; belum dipotong pajak bunga."}


def zakat(argumen):
    jenis = str(argumen.get("jenis_zakat", "maal")).lower()
    if jenis == "fitrah":
        jiwa = int(angka(argumen, "jumlah_jiwa", 1, minimal=1))
        harga_beras = argumen.get("harga_beras_per_kg")
        hasil = {"jenis": "fitrah", "jumlah_jiwa": jiwa, "beras_kg": BERAS_FITRAH_KG * jiwa}
        if harga_beras not in (None, ""):
            hasil["perkiraan_uang"] = rupiah(BERAS_FITRAH_KG * jiwa * angka(argumen, "harga_beras_per_kg"))
        hasil["catatan"] = "Nilai uang zakat fitrah biasanya ditetapkan BAZNAS daerah setiap tahun."
        return hasil

    jumlah = angka(argumen, "jumlah")
    harga_emas = argumen.get("harga_emas_per_gram")
    nisab = NISAB_GRAM_EMAS * angka(argumen, "harga_emas_per_gram") if harga_emas not in (None, "") else None
    if jenis == "penghasilan" and nisab is not None:
        # BAZNAS: nisab penghasilan per bulan = nisab emas setahun dibagi 12
        nisab = nisab / 12
    hasil = {"jenis": jenis, "jumlah": rupiah(jumlah), "zakat_jika_wajib": rupiah(jumlah * KADAR_ZAKAT), "kadar": "2,5%"}
    if nisab is None:
        hasil["catatan"] = "Nisab belum dihitung karena harga emas per gram tidak diisi (nisab = 85 gram emas)."
    else:
        hasil["nisab"] = rupiah(nisab)
        hasil["wajib"] = jumlah >= nisab
        hasil["catatan"] = "Zakat maal juga mensyaratkan haul (dimiliki satu tahun)." if jenis == "maal" else "Nisab penghasilan per bulan mengikuti BAZNAS."
    return hasil


def pph21(argumen):
    """Perkiraan PPh 21 setahun untuk pegawai tetap dengan tarif progresif UU HPP."""
    gaji = angka(argumen, "gaji_bruto_bulanan", minimal=0)
    bulan = int(angka(argumen, "jumlah_bulan", 12, minimal=1))
    iuran = angka(argumen, "iuran_pensiun_bulanan", 0)
    kawin = str(argumen.get("status_kawin", "tidak")).lower() in ("ya", "kawin", "k", "menikah", "true")
    tanggungan = min(int(angka(argumen, "tanggungan", 0)), 3)
    if bulan > 12:
        raise GalatAlat("jumlah_bulan paling banyak 12")

    bruto = gaji * bulan
    biaya_jabatan = min(bruto * 0.05, BIAYA_JABATAN_MAKS * bulan / 12)
    neto = bruto - biaya_jabatan - iuran * bulan
    # penghasilan neto disetahunkan untuk menentukan lapisan tarif
    neto_setahun = neto * 12 / bulan
    ptkp = PTKP_DIRI + (PTKP_KAWIN if kawin else 0) + PTKP_TANGGUNGAN * tanggungan
    pkp = max(math.floor((neto_setahun - ptkp) / 1000) * 1000, 0)

    pajak = 0.0
    bawah = 0
    rincian = []
    for atas, tarif in LAPISAN_PPH:
        if pkp <= bawah:
            break
        bagian = min(pkp, atas) - bawah
        pajak += bagian * tarif
        rincian.append({"lapisan": f"{tarif:.0%}", "penghasilan": rupiah(bagian), "pajak": rupiah(bagian * tarif)})
        bawah = atas
    pajak_periode = pajak * bulan / 12
    return {"penghasilan_bruto": rupiah(bruto), "biaya_jabatan": rupiah(biaya_jabatan), "penghasilan_neto": rupiah(neto),
            "ptkp_setahun": ptkp, "status_ptkp": f"{'K' if kawin else 'TK'}/{tanggungan}", "pkp_setahun": pkp,
            "rincian_tarif": rincian, "pph21_setahun": rupiah(pajak), f"pph21_{bulan}_bulan": rupiah(pajak_periode),
            "rata_rata_per_bulan": rupiah(pajak_periode / bulan),
            "catatan": "Perkiraan setahun dengan tarif UU HPP. Potongan bulanan memakai tarif efektif rata-rata (TER) "
                       "sehingga bisa berbeda tiap bulan, lalu disesuaikan di bulan terakhir."}


class AlatKeuangan:
    def jalankan(self, argumen):
        jenis = str(argumen.get("jenis", "")).lower()
        fungsi = {"cicilan": cicilan, "kredit": cicilan, "bunga_majemuk": bunga_majemuk, "investasi": bunga_majemuk,
                  "zakat": zakat, "pph21": pph21, "pajak": pph21}.get(jenis)
        if fungsi is None:
            raise GalatAlat("jenis harus cicilan, bunga_majemuk, zakat, atau pph21")
        return fungsi(argumen)