import logging
import os
import re

import prompt

TANDA_SEMBUNYI = "[disembunyikan]"
JAWABAN_BOCOR = "Maaf, saya tidak bisa membagikan instruksi atau pengaturan internal saya. Ada hal lain yang bisa saya bantu?"
# nama variabel lingkungan yang nilainya rahasia
POLA_NAMA_RAHASIA = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|PASS|KUNCI|RAHASIA|CREDENTIAL", re.IGNORECASE)
PANJANG_RAHASIA_MIN = 8
# pola kunci yang umum walaupun bukan milik agent ini
POLA_KUNCI_UMUM = re.compile(
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_-]{20,}|\bAIza[0-9A-Za-z_-]{35}\b|\bgh[pousr]_[A-Za-z0-9]{36,}\b|"
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}|\btvly-[A-Za-z0-9_-]{20,}|\bxkeysib-[A-Za-z0-9-]{20,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")
# NAMA_KEY=nilai di baris .env: nilai acak panjang (huruf dan angka) disembunyikan, contoh seperti "isi_kunci_anda" dibiarkan
POLA_BARIS_ENV = re.compile(r"\b([A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD))(\s*[=:]\s*[\"']?)((?=[A-Za-z0-9_\-/+]*\d)(?=[A-Za-z0-9_\-/+]*[A-Za-z])[A-Za-z0-9_\-/+]{20,})")
# kata sandi di alamat database, misalnya postgres://user:sandi@host
POLA_SANDI_URL = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)([^\s@/]+)(@)")
# isian contoh di alamat database tidak perlu disembunyikan
POLA_SANDI_CONTOH = re.compile(r"(?i)(?:your_?)?(?:password|passwd|pass|pwd|sandi|kata_?sandi|secret|rahasia)|\*+|<[^>]*>|\$\{?\w+\}?")
PANJANG_BARIS_INSTRUKSI = 60
BATAS_BARIS_BOCOR = 2


def rahasia_lingkungan():
    """Nilai variabel lingkungan yang namanya menandakan rahasia (API key, token, kata sandi)."""
    return [nilai for nama, nilai in os.environ.items() if POLA_NAMA_RAHASIA.search(nama) and len(nilai.strip()) >= PANJANG_RAHASIA_MIN]


def baris_instruksi():
    """Baris panjang dari semua instruksi di prompt.py, untuk mengenali jawaban yang menyalin instruksi sistem."""
    semua = [nilai for nama, nilai in vars(prompt).items() if nama.isupper() and isinstance(nilai, str)]
    semua += [nilai for nilai in prompt.ATURAN_ALAT.values() if isinstance(nilai, str)]
    return sorted({b.strip() for teks in semua for b in teks.splitlines() if len(b.strip()) >= PANJANG_BARIS_INSTRUKSI})


class PenyaringKeluaran:
    """Memeriksa jawaban sebelum sampai ke pengguna: kunci dan kata sandi diganti [disembunyikan],
    dan jawaban yang menyalin instruksi sistem diganti penolakan."""

    def __init__(self, rahasia=None, instruksi=None):
        nilai = rahasia_lingkungan() if rahasia is None else rahasia
        self.rahasia = sorted({r.strip() for r in nilai if len(r.strip()) >= PANJANG_RAHASIA_MIN}, key=len, reverse=True)
        self.instruksi = [b[:PANJANG_BARIS_INSTRUKSI] for b in (baris_instruksi() if instruksi is None else instruksi)]

    def bocor_instruksi(self, teks):
        return sum(b in teks for b in self.instruksi) >= BATAS_BARIS_BOCOR

    def saring(self, teks):
        """Mengembalikan (teks aman, alasan); alasan kosong jika tidak ada yang diubah."""
        if not isinstance(teks, str) or not teks:
            return teks, ""
        if self.bocor_instruksi(teks):
            return JAWABAN_BOCOR, "menyalin instruksi sistem"
        aman = teks
        for r in self.rahasia:
            aman = aman.replace(r, TANDA_SEMBUNYI)
        aman = POLA_KUNCI_UMUM.sub(TANDA_SEMBUNYI, aman)
        aman = POLA_BARIS_ENV.sub(lambda c: c.group(1) + c.group(2) + TANDA_SEMBUNYI, aman)
        aman = POLA_SANDI_URL.sub(lambda c: c.group(0) if POLA_SANDI_CONTOH.fullmatch(c.group(2)) else c.group(1) + TANDA_SEMBUNYI + c.group(3), aman)
        return aman, ("berisi kunci atau kata sandi" if aman != teks else "")

    def saring_hasil(self, hasil):
        """Menyaring jawaban akhir agent (dict hasil), email yang akan dikirim, dan saran pertanyaan, lalu mencatat bila ada yang disembunyikan."""
        if not isinstance(hasil, dict):
            return hasil
        alasan = set()

        def saring(teks):
            aman, sebab = self.saring(teks)
            if sebab:
                alasan.add(sebab)
            return aman

        hasil["jawaban"] = saring(hasil.get("jawaban"))
        email = hasil.get("email")
        if isinstance(email, dict):
            hasil["email"] = {k: saring(v) for k, v in email.items()}
        if isinstance(hasil.get("saran"), list):
            hasil["saran"] = [saring(s) for s in hasil["saran"]]
        if alasan:
            logging.warning("jawaban disaring: %s", ", ".join(sorted(alasan)))
        return hasil


class AliranAman:
    """Potongan teks stream ditahan sebanyak TAHAN huruf terakhir, agar rahasia yang baru datang sebagian
    tidak sempat terkirim sebelum dikenali dan disembunyikan."""

    TAHAN = 160

    def __init__(self, penyaring, kirim):
        self.penyaring = penyaring
        self.kirim = kirim
        self.teks = ""
        self.terkirim = 0
        self.berhenti = False

    def kabar(self, jenis, isi):
        if jenis == "ulang":
            # model memulai jawaban dari awal, jadi tampungan ikut dikosongkan
            self.teks, self.terkirim, self.berhenti = "", 0, False
        elif jenis == "teks":
            self.teks += str(isi.get("teks", ""))
            if self.berhenti:
                return
            aman, alasan = self.penyaring.saring(self.teks)
            if alasan == "menyalin instruksi sistem":
                # teks yang sudah tampil dihapus, dan sisanya baru muncul sebagai jawaban akhir yang sudah disaring
                self.berhenti = True
                self.kirim("ulang", {})
                return
            batas = len(aman) - self.TAHAN
            if batas > self.terkirim:
                self.kirim("teks", {"teks": aman[self.terkirim:batas]})
                self.terkirim = batas
            return
        self.kirim(jenis, isi)
