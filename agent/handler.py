import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler

from llm.client import GalatLLM
from pengaman.aturan import GalatPengaman

BATAS_BODY = 64_000


def buat_penangan(agen, api_key):
    """Membuat kelas penangan HTTP yang sudah membawa agen dan API key."""

    class Penangan(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/kesehatan":
                self.kirim_json(200, {"status": "sukses", "message": "layanan agent aktif"})
                return
            self.kirim_json(404, {"status": "gagal", "message": "alamat tidak ditemukan"})

        def do_POST(self):
            if self.path != "/jawab":
                self.kirim_json(404, {"status": "gagal", "message": "alamat tidak ditemukan"})
                return

            if not hmac.compare_digest(self.headers.get("X-API-Key", ""), api_key):
                self.kirim_json(401, {"status": "gagal", "message": "API key tidak valid"})
                return

            panjang = int(self.headers.get("Content-Length") or 0)
            if panjang <= 0 or panjang > BATAS_BODY:
                self.kirim_json(400, {"status": "gagal", "message": "ukuran body tidak valid"})
                return

            try:
                data = json.loads(self.rfile.read(panjang))
                if not isinstance(data, dict):
                    raise ValueError
            except ValueError:
                self.kirim_json(400, {"status": "gagal", "message": "body JSON tidak valid"})
                return

            try:
                hasil = agen.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"))
            except GalatPengaman as galat:
                self.kirim_json(400, {"status": "gagal", "message": str(galat)})
                return
            except GalatLLM as galat:
                logging.error("LLM gagal: %s", galat)
                self.kirim_json(502, {"status": "gagal", "message": "layanan AI sedang bermasalah"})
                return
            except Exception:
                logging.exception("galat tak terduga")
                self.kirim_json(500, {"status": "gagal", "message": "agent sedang bermasalah"})
                return

            self.kirim_json(200, {"status": "sukses", "message": "jawaban agent", "data": hasil})

        def kirim_json(self, status, data):
            badan = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(badan)))
            self.end_headers()
            self.wfile.write(badan)

    return Penangan