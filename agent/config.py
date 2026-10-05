import os
from dataclasses import dataclass
from pathlib import Path

FOLDER_AGENT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    host: str
    port: int
    api_key: str
    gemini_api_key: str
    gemini_model: str
    tavily_api_key: str
    maks_langkah: int
    maks_baca_url: int
    batas_waktu: int
    domain_diblokir: list


def baca_env(path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as berkas:
        for baris in berkas:
            baris = baris.strip()
            if not baris or baris.startswith("#") or "=" not in baris:
                continue
            kunci, nilai = baris.split("=", 1)
            os.environ.setdefault(kunci.strip(), nilai.strip())


def ambil(kunci, bawaan=""):
    return os.environ.get(kunci, "") or bawaan


def ambil_angka(kunci, bawaan):
    try:
        nilai = int(os.environ.get(kunci, ""))
    except ValueError:
        return bawaan
    return nilai if nilai > 0 else bawaan


def muat():
    """Membaca .env lalu mengisi Config."""
    baca_env(FOLDER_AGENT / ".env")

    diblokir = [d.strip().lower() for d in ambil("AGENT_DOMAIN_DIBLOKIR").split(",") if d.strip()]

    return Config(
        host=ambil("AGENT_HOST", "127.0.0.1"),
        port=ambil_angka("AGENT_PORT", 8082),
        api_key=ambil("AGENT_API_KEY"),
        gemini_api_key=ambil("GEMINI_API_KEY"),
        gemini_model=ambil("GEMINI_MODEL", "gemini-3.8-flash"),
        tavily_api_key=ambil("TAVILY_API_KEY"),
        maks_langkah=ambil_angka("AGENT_MAKS_LANGKAH", 4),
        maks_baca_url=ambil_angka("AGENT_MAKS_BACA_URL", 3),
        batas_waktu=ambil_angka("AGENT_BATAS_WAKTU_DETIK", 15),
        domain_diblokir=diblokir,
    )