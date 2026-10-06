import json
import urllib.error
import urllib.request


class GalatLLM(Exception):
    def __init__(self, pesan, kode=0):
        super().__init__(pesan)
        self.kode = kode


def kirim_json(alamat, badan, header, batas_waktu, nama):
    """Mengirim JSON lewat POST dan mengembalikan JSON balasan; semua kegagalan dijadikan GalatLLM."""
    permintaan = urllib.request.Request(alamat, data=badan, headers=header, method="POST")
    try:
        with urllib.request.urlopen(permintaan, timeout=batas_waktu) as respon:
            return json.load(respon)
    except urllib.error.HTTPError as galat:
        detail = galat.read().decode("utf-8", "replace")[:300]
        raise GalatLLM(f"{nama} menolak ({galat.code}): {detail}", galat.code)
    except (urllib.error.URLError, TimeoutError, ValueError) as galat:
        raise GalatLLM(f"{nama} tidak bisa dihubungi: {galat}")


def buat_klien(cfg):
    """Memilih klien LLM sesuai LLM_PROVIDER dan mengembalikan (klien, nama model)."""
    if cfg.llm_provider == "aws":
        from llm.aws import KlienAWS

        if cfg.aws_auth_mode != "iam":
            raise ValueError("AWS_AUTH_MODE hanya mendukung nilai iam")
        if not cfg.aws_access_key_id or not cfg.aws_secret_access_key:
            raise ValueError("AWS_ACCESS_KEY_ID dan AWS_SECRET_ACCESS_KEY wajib diisi di .env")
        if not cfg.llm_model:
            raise ValueError("LLM_MODEL wajib diisi di .env")
        klien = KlienAWS(cfg.aws_access_key_id, cfg.aws_secret_access_key, cfg.aws_region, cfg.llm_model)
        return klien, cfg.llm_model

    if cfg.llm_provider == "api":
        from llm.api import KlienAPI

        if not cfg.api_url or not cfg.api_key_llm or not cfg.api_model:
            raise ValueError("API_URL, API_KEY, dan API_MODEL wajib diisi di .env")
        return KlienAPI(cfg.api_url, cfg.api_key_llm, cfg.api_model), cfg.api_model

    if cfg.llm_provider == "local":
        from llm.api import KlienAPI

        if not cfg.local_url or not cfg.local_model:
            raise ValueError("LOCAL_URL dan LOCAL_MODEL wajib diisi di .env")
        return KlienAPI(cfg.local_url, "", cfg.local_model, batas_waktu=180), cfg.local_model

    raise ValueError("LLM_PROVIDER harus salah satu dari: aws, api, local")