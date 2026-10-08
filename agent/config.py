import os
from dataclasses import dataclass
from pathlib import Path

FOLDER_AGENT = Path(__file__).resolve().parent


@dataclass
class Config:
    host: str
    port: int
    api_key: str
    llm_provider: str
    aws_auth_mode: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    llm_model: str
    api_url: str
    api_key_llm: str
    api_model: str
    local_url: str
    local_model: str
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
        port=ambil_angka("AGENT_PORT", ambil_angka("PORT", 8082)),
        api_key=ambil("AGENT_API_KEY"),
        llm_provider=ambil("LLM_PROVIDER", "aws").lower(),
        aws_auth_mode=ambil("AWS_AUTH_MODE", "iam").lower(),
        aws_access_key_id=ambil("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=ambil("AWS_SECRET_ACCESS_KEY"),
        aws_region=ambil("AWS_REGION", "ap-southeast-3"),
        llm_model=ambil("LLM_MODEL"),
        api_url=ambil("API_URL"),
        api_key_llm=ambil("API_KEY"),
        api_model=ambil("API_MODEL"),
        local_url=ambil("LOCAL_URL", "http://127.0.0.1:11434/v1"),
        local_model=ambil("LOCAL_MODEL"),
        tavily_api_key=ambil("TAVILY_API_KEY"),
        maks_langkah=ambil_angka("AGENT_MAKS_LANGKAH", 6),
        maks_baca_url=ambil_angka("AGENT_MAKS_BACA_URL", 3),
        batas_waktu=ambil_angka("AGENT_BATAS_WAKTU_DETIK", 15),
        domain_diblokir=diblokir,
    )