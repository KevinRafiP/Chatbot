import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from alat.jaringan import GalatAlat

BERKAS_PROSES = Path(__file__).resolve().with_name("kalkulus_proses.py")


def sympy_tersedia():
    return importlib.util.find_spec("sympy") is not None


class AlatKalkulus:
    """Turunan, integral, limit, dan persamaan memakai SymPy di proses terpisah yang dibatasi waktunya."""

    def __init__(self, p):
        self.batas_detik = p.kalkulus_batas_detik

    def jalankan(self, argumen):
        masukan = {k: argumen.get(k) for k in ("operasi", "ekspresi", "variabel", "orde", "batas_bawah", "batas_atas", "menuju", "arah")}
        try:
            proses = subprocess.run([sys.executable, "-I", str(BERKAS_PROSES)], input=json.dumps(masukan), capture_output=True,
                                    text=True, timeout=self.batas_detik)
        except subprocess.TimeoutExpired:
            raise GalatAlat(f"soal terlalu berat, tidak selesai dalam {self.batas_detik} detik")
        try:
            hasil = json.loads(proses.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            raise GalatAlat("kalkulus gagal dijalankan")
        if "galat" in hasil:
            raise GalatAlat(hasil["galat"])
        return hasil