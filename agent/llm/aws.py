import json
import urllib.parse

from llm.client import GalatLLM, kirim_json
from llm.tanda_tangan import tanda_tangani

MAKS_TOKEN_JAWABAN = 1024


class KlienAWS:
    def __init__(self, access_key, secret_key, wilayah, model, batas_waktu=60):
        self.access_key = access_key
        self.secret_key = secret_key
        self.wilayah = wilayah
        self.model = model
        self.batas_waktu = batas_waktu
        self.alamat = f"https://bedrock-runtime.{wilayah}.amazonaws.com"

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None):
        """Mengirim percakapan ke Amazon Bedrock (Converse) dan mengembalikan pesan balasan model."""
        badan = {
            "system": [{"text": instruksi_sistem}],
            "messages": isi_percakapan,
            "inferenceConfig": {"maxTokens": MAKS_TOKEN_JAWABAN},
        }
        if deklarasi_alat:
            badan["toolConfig"] = {"tools": [ubah_alat(d) for d in deklarasi_alat]}

        alamat = f"{self.alamat}/model/{urllib.parse.quote(self.model, safe='')}/converse"
        data_kirim = json.dumps(badan).encode("utf-8")
        header = tanda_tangani("POST", alamat, data_kirim, self.wilayah, "bedrock",
                               self.access_key, self.secret_key, {"Content-Type": "application/json"})
        data = kirim_json(alamat, data_kirim, header, self.batas_waktu, "Bedrock")

        pesan = (data.get("output") or {}).get("message")
        if not pesan or not pesan.get("content"):
            raise GalatLLM(f"Bedrock tidak memberi jawaban (alasan berhenti: {data.get('stopReason')})")
        return pesan


def ubah_alat(deklarasi):
    """Mengubah deklarasi alat milik agent ke bentuk toolSpec yang diminta Bedrock."""
    return {
        "toolSpec": {
            "name": deklarasi["name"],
            "description": deklarasi["description"],
            "inputSchema": {"json": deklarasi["parameters"]},
        }
    }