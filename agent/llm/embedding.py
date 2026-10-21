import json
import logging
import urllib.parse

from llm.client import GalatLLM, kirim_json
from llm.tanda_tangan import tanda_tangani

MAKS_TEKS = 96
PENYEDIA_EMBED = ("aws", "api", "local")
MODEL_BEDROCK = ("cohere.embed-", "amazon.titan-embed-text-v2")
JENIS_COHERE = {"dokumen": "search_document", "kueri": "search_query"}
JENIS_GEMINI = {"dokumen": "RETRIEVAL_DOCUMENT", "kueri": "RETRIEVAL_QUERY"}
# 768 dimensi sudah cukup teliti dan masih bisa diberi indeks HNSW (pgvector maksimal 2000 dimensi)
DIMENSI_GEMINI = 768


class PembuatEmbedding:
    """Mengubah teks menjadi vektor makna lewat EMBED_PROVIDER: aws (Bedrock), api (Gemini atau layanan
    berformat OpenAI), atau local (Ollama, langsung atau lewat gerbang local dan ngrok)."""

    def __init__(self, cfg, batas_waktu=30):
        self.cfg = cfg
        self.penyedia = cfg.embed_provider
        self.model = cfg.embed_model
        self.batas_waktu = batas_waktu

    def info(self):
        return {"aktif": True, "model": self.model, "skor_minimal": self.cfg.embed_skor_minimal}

    def buat(self, daftar_teks, jenis):
        """jenis "dokumen" untuk data yang disimpan, "kueri" untuk pertanyaan pengguna."""
        if self.penyedia == "aws":
            daftar_vektor = self.bedrock(daftar_teks, jenis)
        elif self.penyedia == "api" and self.model.startswith("gemini-embedding"):
            daftar_vektor = self.gemini(daftar_teks, jenis)
        elif self.penyedia == "api":
            daftar_vektor = self.openai(self.cfg.embed_api_url, self.cfg.embed_api_key, daftar_teks)
        else:
            daftar_vektor = self.openai(self.cfg.embed_local_url, self.cfg.embed_local_api_key, daftar_teks)
        if len(daftar_vektor) != len(daftar_teks):
            raise GalatLLM(f"penyedia embedding mengembalikan {len(daftar_vektor)} vektor untuk {len(daftar_teks)} teks")
        # 6 angka di belakang koma sudah cukup teliti dan membuat balasan JSON jauh lebih kecil
        return [[round(nilai, 6) for nilai in vektor] for vektor in daftar_vektor]

    def openai(self, alamat, kunci, daftar_teks):
        """Format OpenAI /embeddings, dipakai Ollama, OpenAI, dan layanan sejenis."""
        header = {"Content-Type": "application/json"}
        if kunci:
            header["Authorization"] = f"Bearer {kunci}"
        badan = json.dumps({"model": self.model, "input": daftar_teks}).encode("utf-8")
        data = kirim_json(f"{alamat.rstrip('/')}/embeddings", badan, header, self.batas_waktu, "Layanan embedding")
        hasil = sorted(data.get("data") or [], key=lambda isi: isi.get("index", 0))
        return [isi.get("embedding") or [] for isi in hasil]

    def gemini(self, daftar_teks, jenis):
        daftar_permintaan = []
        for teks in daftar_teks:
            permintaan = {"model": f"models/{self.model}", "outputDimensionality": DIMENSI_GEMINI}
            if self.model == "gemini-embedding-001":
                permintaan["taskType"] = JENIS_GEMINI[jenis]
            else:
                # Gemini Embedding 2 tidak menerima taskType; jenis tugas ditulis sebagai awalan teks
                teks = awalan_gemini(teks, jenis)
            permintaan["content"] = {"parts": [{"text": teks}]}
            daftar_permintaan.append(permintaan)
        badan = {"requests": daftar_permintaan}
        alamat = f"{self.cfg.embed_api_url.rstrip('/')}/models/{urllib.parse.quote(self.model, safe='')}:batchEmbedContents"
        header = {"Content-Type": "application/json", "x-goog-api-key": self.cfg.embed_api_key}
        data = kirim_json(alamat, json.dumps(badan).encode("utf-8"), header, self.batas_waktu, "Gemini embedding")
        return [isi.get("values") or [] for isi in data.get("embeddings") or []]

    def bedrock(self, daftar_teks, jenis):
        if self.model.startswith("cohere.embed-"):
            data = self.panggil_bedrock({"texts": daftar_teks, "input_type": JENIS_COHERE[jenis], "truncate": "END"})
            vektor = data.get("embeddings")
            return (vektor.get("float") if isinstance(vektor, dict) else vektor) or []
        # Titan hanya menerima satu teks per panggilan dan tidak membedakan dokumen dengan kueri
        return [self.panggil_bedrock({"inputText": teks, "dimensions": 1024, "normalize": True}).get("embedding") or []
                for teks in daftar_teks]

    def panggil_bedrock(self, badan):
        wilayah = self.cfg.embed_region
        alamat = f"https://bedrock-runtime.{wilayah}.amazonaws.com/model/{urllib.parse.quote(self.model, safe='')}/invoke"
        data_kirim = json.dumps(badan).encode("utf-8")
        header = tanda_tangani("POST", alamat, data_kirim, wilayah, "bedrock", self.cfg.aws_access_key_id,
                               self.cfg.aws_secret_access_key, {"Content-Type": "application/json"})
        return kirim_json(alamat, data_kirim, header, self.batas_waktu, "Bedrock embedding")


def awalan_gemini(teks, jenis):
    """Format tugas Gemini Embedding 2; backend mengirim dokumen sebagai "judul" + baris baru + "isi"."""
    if jenis == "kueri":
        return f"task: search result | query: {teks}"
    judul, _, isi = teks.partition("\n")
    return f"title: {judul.strip() or 'none'} | text: {isi.strip() or judul}"


def buat_pembuat_embedding(cfg):
    """Mengembalikan None jika EMBED_PROVIDER kosong atau pengaturannya kurang; agent tetap jalan tanpa embedding."""
    penyedia = cfg.embed_provider
    if not penyedia:
        logging.info("EMBED_PROVIDER kosong: pencarian makna mati, pengetahuan dicari dengan kata kunci")
        return None

    masalah = ""
    if penyedia not in PENYEDIA_EMBED:
        masalah = "EMBED_PROVIDER harus salah satu dari: aws, api, local"
    elif not cfg.embed_model:
        masalah = "EMBED_MODEL kosong"
    elif penyedia == "aws" and not (cfg.aws_access_key_id and cfg.aws_secret_access_key):
        masalah = "AWS_ACCESS_KEY_ID dan AWS_SECRET_ACCESS_KEY wajib diisi"
    elif penyedia == "aws" and not cfg.embed_model.startswith(MODEL_BEDROCK):
        masalah = f"model Bedrock {cfg.embed_model} belum didukung (cohere.embed-* atau amazon.titan-embed-text-v2*)"
    elif penyedia == "api" and not cfg.embed_api_key:
        masalah = "EMBED_API_KEY (atau API_KEY) wajib diisi"
    if masalah:
        logging.warning("pencarian makna mati: %s", masalah)
        return None

    logging.info("pencarian makna aktif: %s, model %s", penyedia, cfg.embed_model)
    return PembuatEmbedding(cfg)