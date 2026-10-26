import secrets
import string

from alat.jaringan import GalatAlat

HURUF_SANDI = string.ascii_letters + string.digits
SIMBOL_SANDI = "!@#$%^&*-_=+?"
MAKS_PILIHAN = 100


def bilangan(argumen, nama, bawaan, minimal, maksimal):
    try:
        nilai = int(float(argumen.get(nama) if argumen.get(nama) not in (None, "") else bawaan))
    except (TypeError, ValueError):
        raise GalatAlat(f"{nama} harus angka bulat")
    if not minimal <= nilai <= maksimal:
        raise GalatAlat(f"{nama} harus antara {minimal} dan {maksimal}")
    return nilai


def daftar_pilihan(argumen):
    pilihan = argumen.get("pilihan") or []
    if isinstance(pilihan, str):
        pilihan = [bagian.strip() for bagian in pilihan.split(",")]
    pilihan = [str(p).strip()[:200] for p in pilihan if str(p).strip()][:MAKS_PILIHAN]
    if len(pilihan) < 2:
        raise GalatAlat("pilihan minimal 2")
    return pilihan


class AlatAcak:
    """Pengacak yang memakai modul secrets, jadi hasilnya tidak bisa ditebak."""

    def jalankan(self, argumen):
        jenis = str(argumen.get("jenis", "angka")).lower()
        jumlah = bilangan(argumen, "jumlah", 1, 1, 20)
        if jenis == "kata_sandi":
            panjang = bilangan(argumen, "panjang", 16, 8, 64)
            huruf = HURUF_SANDI + (SIMBOL_SANDI if argumen.get("simbol", True) else "")
            return {"kata_sandi": ["".join(secrets.choice(huruf) for _ in range(panjang)) for _ in range(jumlah)]}
        if jenis == "dadu":
            sisi = bilangan(argumen, "sisi", 6, 2, 1000)
            lemparan = [secrets.randbelow(sisi) + 1 for _ in range(jumlah)]
            return {"sisi": sisi, "hasil": lemparan, "total": sum(lemparan)}
        if jenis == "koin":
            return {"hasil": [secrets.choice(["Angka", "Gambar"]) for _ in range(jumlah)]}
        if jenis == "pilih":
            pilihan = daftar_pilihan(argumen)
            jumlah = min(jumlah, len(pilihan))
            terpilih = pilihan[:]
            secrets.SystemRandom().shuffle(terpilih)
            return {"terpilih": terpilih[:jumlah], "dari": len(pilihan)}
        if jenis == "urutan":
            pilihan = daftar_pilihan(argumen)
            secrets.SystemRandom().shuffle(pilihan)
            return {"urutan": pilihan}
        minimal = bilangan(argumen, "min", 1, -10 ** 12, 10 ** 12)
        maksimal = bilangan(argumen, "max", 100, -10 ** 12, 10 ** 12)
        if minimal > maksimal:
            minimal, maksimal = maksimal, minimal
        return {"min": minimal, "max": maksimal, "hasil": [minimal + secrets.randbelow(maksimal - minimal + 1) for _ in range(jumlah)]}