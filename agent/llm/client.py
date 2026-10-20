import json
import logging
import urllib.error
import urllib.request


class GalatLLM(Exception):
    def __init__(self, pesan, kode=0):
        super().__init__(pesan)
        self.kode = kode


def kirim_json(alamat, badan, header, batas_waktu, nama):
    """Mengirim JSON lewat POST dan mengembalikan JSON balasan; semua kegagalan dijadikan GalatLLM."""
    with buka(alamat, badan, header, batas_waktu, nama) as respon:
        try:
            return json.load(respon)
        except TimeoutError:
            raise GalatLLM(f"{nama} diam lebih dari {batas_waktu} detik", 204)
        except (ValueError, OSError) as galat:
            raise GalatLLM(f"{nama} tidak bisa dihubungi: {galat}")

def buka(alamat, badan, header, batas_waktu, nama):
    """Mengirim POST dan mengembalikan respons yang masih terbuka, agar balasan stream bisa dibaca sedikit demi sedikit."""
    permintaan = urllib.request.Request(alamat, data=badan, headers=header, method="POST")
    try:
        return urllib.request.urlopen(permintaan, timeout=batas_waktu)
    except urllib.error.HTTPError as galat:
        detail = galat.read().decode("utf-8", "replace")[:300]
        jenis = galat.headers.get("x-amzn-ErrorType", "")
        raise GalatLLM(f"{nama} menolak ({galat.code}) {jenis}: {detail}", galat.code)
    except (urllib.error.URLError, TimeoutError, ValueError) as galat:
        # model yang terlalu lama diam diberi kode 204 agar bisa diulang tanpa paksaan alat atau ke model cadangan
        if isinstance(galat, TimeoutError) or isinstance(getattr(galat, "reason", None), TimeoutError):
            raise GalatLLM(f"{nama} diam lebih dari {batas_waktu} detik", 204)
        raise GalatLLM(f"{nama} tidak bisa dihubungi: {galat}")


# galat yang layak diulang ke model cadangan: tidak terhubung atau timeout (0), jawaban kosong (204), antrean penuh, dan gangguan server
KODE_PAKAI_CADANGAN = {0, 204, 408, 429}


class KlienCadangan:
    """Membungkus klien utama; jika gagal sebelum ada teks yang terkirim, permintaan yang sama diulang sekali ke model cadangan."""

    def __init__(self, utama, cadangan):
        self.utama = utama
        self.cadangan = cadangan

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None, wajib_alat=False, saat_teks=None):
        terkirim = []

        def teruskan(potongan):
            terkirim.append(potongan)
            saat_teks(potongan)

        try:
            return self.utama.kirim(instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, teruskan if saat_teks else None)
        except GalatLLM as galat:
            if terkirim or (galat.kode not in KODE_PAKAI_CADANGAN and galat.kode < 500):
                raise
            logging.warning("model utama gagal, dicoba model cadangan: %s", galat)
        return self.cadangan.kirim(instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, saat_teks)


def buat_klien(cfg, model=""):
    """Memilih klien LLM sesuai LLM_PROVIDER dan mengembalikan (klien, nama model); model kosong berarti model utama."""
    if cfg.llm_provider == "aws":
        from llm.aws import KlienAWS

        if cfg.aws_auth_mode != "iam":
            raise ValueError("AWS_AUTH_MODE hanya mendukung nilai iam")
        if not cfg.aws_access_key_id or not cfg.aws_secret_access_key:
            raise ValueError("AWS_ACCESS_KEY_ID dan AWS_SECRET_ACCESS_KEY wajib diisi di .env")
        model = model or cfg.llm_model
        if not model:
            raise ValueError("LLM_MODEL wajib diisi di .env")
        return KlienAWS(cfg.aws_access_key_id, cfg.aws_secret_access_key, cfg.aws_region, model), model

    if cfg.llm_provider == "api":
        from llm.api import KlienAPI

        model = model or cfg.api_model
        if not cfg.api_url or not cfg.api_key_llm or not model:
            raise ValueError("API_URL, API_KEY, dan API_MODEL wajib diisi di .env")
        return KlienAPI(cfg.api_url, cfg.api_key_llm, model), model

    if cfg.llm_provider == "local":
        from llm.api import KlienAPI

        model = model or cfg.local_model
        if not cfg.local_url or not model:
            raise ValueError("LOCAL_URL dan LOCAL_MODEL wajib diisi di .env")
        return KlienAPI(cfg.local_url, cfg.local_api_key, model, batas_waktu=180), model

    raise ValueError("LLM_PROVIDER harus salah satu dari: aws, api, local")