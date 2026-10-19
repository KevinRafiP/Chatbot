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
            if self.path not in ("/jawab", "/jawab-stream", "/ringkas"):
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
            if self.path == "/jawab-stream":
                self.jawab_stream(data)
                return
            try:
                if self.path == "/ringkas":
                    hasil = {"ingatan": agen.ringkas(data.get("ingatan"), data.get("riwayat"))}
                else:
                    hasil = agen.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"))
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

        def jawab_stream(self, data):
            """Mengirim jawaban sebagai Server-Sent Events: status langkah, potongan teks, lalu hasil akhir."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def kabar(jenis, isi):
                self.wfile.write(f"event: {jenis}\ndata: {json.dumps(isi, ensure_ascii=False)}\n\n".encode("utf-8"))

            try:
                hasil = agen.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"), kabar)
                kabar("selesai", hasil)
            except (BrokenPipeError, ConnectionResetError):
                logging.info("backend menutup stream sebelum jawaban selesai")
            except GalatPengaman as galat:
                kabar("galat", {"message": str(galat)})
            except GalatLLM as galat:
                logging.error("LLM gagal: %s", galat)
                kabar("galat", {"message": "layanan AI sedang bermasalah"})
            except Exception:
                logging.exception("galat tak terduga")
                kabar("galat", {"message": "agent sedang bermasalah"})

        def kirim_json(self, status, data):
            badan = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(badan)))
            self.end_headers()
            self.wfile.write(badan)

    return Penangan