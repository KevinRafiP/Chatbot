import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.request

from alat.jaringan import GalatAlat
from llm import denyut

MAKS_HURUF_KODE = 20000
MAKS_HURUF_KELUARAN = 8000
# browser butuh waktu memuat Pyodide (sekitar 10 MB) saat pertama kali dipakai
WAKTU_MUAT_CLIENT = 30
# client = Pyodide di browser pengguna (laptop atau HP yang sedang dipakai chat); api = layanan berformat Piston
RUNTIME_DIKENAL = ("client", "api")

# kode yang sedang dijalankan browser: id -> [Event, hasil]; dipakai bersama semua thread permintaan
_menunggu = {}
_gembok = threading.Lock()


def terima_hasil(nomor, hasil):
    """Dipanggil penangan /hasil-kode saat browser mengirim hasil; False jika id tidak sedang ditunggu."""
    with _gembok:
        tunggu = _menunggu.get(str(nomor))
    if tunggu is None or not isinstance(hasil, dict):
        return False
    tunggu[1] = hasil
    tunggu[0].set()
    return True


def rapikan(hasil, tempat):
    keluaran = str(hasil.get("keluaran") or "")
    galat = str(hasil.get("galat") or "")
    data = {"keluaran": keluaran[:MAKS_HURUF_KELUARAN], "dijalankan_di": tempat}
    if hasil.get("hasil"):
        data["nilai_akhir"] = str(hasil["hasil"])[:MAKS_HURUF_KELUARAN]
    if galat:
        data["galat"] = galat[-MAKS_HURUF_KELUARAN:]
    if len(keluaran) > MAKS_HURUF_KELUARAN:
        data["catatan"] = "keluaran dipotong"
    if not keluaran and not galat and not hasil.get("hasil"):
        data["catatan"] = "tidak ada keluaran; pakai print() untuk menampilkan hasil"
    return data


class AlatKode:
    """Menjalankan kode Python dari model di luar agent: di browser pengguna (Pyodide) atau di layanan API (Piston)."""

    def __init__(self, p):
        self.runtime = []
        for nama in p.kode_runtime:
            if nama not in RUNTIME_DIKENAL:
                logging.warning("KODE_RUNTIME %s tidak dikenal, dilewati", nama)
            elif nama == "api" and not p.kode_api_url:
                logging.warning("KODE_RUNTIME api butuh KODE_API_URL, dilewati")
            else:
                self.runtime.append(nama)
        self.batas_detik = p.kode_batas_detik
        self.api_url = p.kode_api_url
        self.api_key = p.kode_api_key

    def ada(self):
        return bool(self.runtime)

    def bisa(self, stream):
        """client hanya bisa dipakai saat jawaban dikirim sebagai stream ke browser."""
        return any(nama == "api" or stream for nama in self.runtime)

    def jalankan(self, argumen, catatan):
        kode = str(argumen.get("kode") or "").strip()
        if not kode:
            raise GalatAlat("kode kosong")
        if len(kode) > MAKS_HURUF_KODE:
            raise GalatAlat(f"kode terlalu panjang (maksimal {MAKS_HURUF_KODE} huruf)")
        kabar = catatan.get("kabar")
        for nama in self.runtime:
            if nama == "client" and kabar:
                return self.di_client(kode, kabar)
            if nama == "api":
                return self.di_api(kode)
        raise GalatAlat("tempat menjalankan kode tidak tersedia untuk permintaan ini")

    def di_client(self, kode, kabar):
        """Kode dikirim ke browser lewat event stream "jalankan_kode"; browser mengirim hasilnya ke backend lalu ke /hasil-kode."""
        nomor = secrets.token_urlsafe(24)
        tunggu = [threading.Event(), None]
        with _gembok:
            _menunggu[nomor] = tunggu
        try:
            kabar("jalankan_kode", {"id": nomor, "kode": kode, "batas_detik": self.batas_detik})
            batas = time.monotonic() + self.batas_detik + WAKTU_MUAT_CLIENT
            # selama menunggu, denyut tetap dikirim agar tombol berhenti pengguna langsung ketahuan
            while not tunggu[0].wait(1):
                denyut.detak()
                if time.monotonic() > batas:
                    raise GalatAlat("browser pengguna tidak mengirim hasil kode tepat waktu")
        finally:
            with _gembok:
                _menunggu.pop(nomor, None)
        return rapikan(tunggu[1], "browser pengguna (Pyodide)")

    def di_api(self, kode):
        """Format Piston (POST /api/v2/execute): bisa Piston di laptop atau server sendiri, atau layanan lain yang memberi API key."""
        badan = {"language": "python", "version": "*", "files": [{"name": "main.py", "content": kode}]}
        header = {"Content-Type": "application/json", "User-Agent": "Vokapas/1.0"}
        if self.api_key:
            header["Authorization"] = self.api_key
        permintaan = urllib.request.Request(self.api_url, data=json.dumps(badan).encode("utf-8"), headers=header, method="POST")
        try:
            with urllib.request.urlopen(permintaan, timeout=self.batas_detik + 10) as respon:
                data = json.load(respon)
        except urllib.error.HTTPError as galat:
            raise GalatAlat(f"layanan kode menolak (kode {galat.code})")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as galat:
            logging.warning("layanan kode gagal: %s", galat)
            raise GalatAlat("layanan kode tidak bisa dihubungi")
        jalan = data.get("run") or {}
        hasil = {"keluaran": jalan.get("stdout") or "", "galat": jalan.get("stderr") or data.get("message") or ""}
        if jalan.get("signal") == "SIGKILL":
            hasil["galat"] = (hasil["galat"] + "\nkode dihentikan karena melewati batas waktu atau memori").strip()
        return rapikan(hasil, "layanan API")