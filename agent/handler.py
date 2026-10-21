import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler

from llm.client import GalatLLM
from llm.embedding import MAKS_TEKS
from pengaman.aturan import GalatPengaman

BATAS_BODY = 64_000


def buat_penangan(daftar_agen, api_key, pembuat_embedding=None):
    """Membuat kelas penangan HTTP yang sudah membawa agen per profil (mendalam, cepat, tamu) dan API key."""
    agen = daftar_agen["mendalam"]

    class Penangan(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/kesehatan":
                self.kirim_json(200, {"status": "sukses", "message": "layanan agent aktif"})
                return
            self.kirim_json(404, {"status": "gagal", "message": "alamat tidak ditemukan"})

        def do_POST(self):
            if self.path not in ("/jawab", "/jawab-stream", "/ringkas", "/embed", "/embed-info"):
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
            if self.path == "/embed-info":
                # backend menanyakan model yang aktif, karena semua pengaturan embedding ada di agent
                info = pembuat_embedding.info() if pembuat_embedding else {"aktif": False, "model": "", "skor_minimal": 0}
                self.kirim_json(200, {"status": "sukses", "message": "info embedding", "data": info})
                return
            if self.path == "/embed":
                self.embed(data)
                return
            # profil dipilih backend: "tamu", "cepat", atau "mendalam" (bawaan)
            pilihan = daftar_agen.get(str(data.get("profil")), agen)
            if self.path == "/jawab-stream":
                self.jawab_stream(pilihan, data)
                return
            try:
                if self.path == "/ringkas":
                    hasil = {"ingatan": agen.ringkas(data.get("ingatan"), data.get("riwayat"))}
                else:
                    hasil = pilihan.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"))
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
                
        def embed(self, data):
            """Mengubah daftar teks menjadi vektor; body {"teks": [...], "jenis": "dokumen" atau "kueri"}."""
            if pembuat_embedding is None:
                self.kirim_json(503, {"status": "gagal", "message": "embedding tidak aktif: periksa EMBED_PROVIDER di agent"})
                return
            daftar_teks, jenis = data.get("teks"), data.get("jenis")
            if (jenis not in ("dokumen", "kueri") or not isinstance(daftar_teks, list) or not 0 < len(daftar_teks) <= MAKS_TEKS
                    or not all(isinstance(teks, str) and teks.strip() for teks in daftar_teks)):
                self.kirim_json(400, {"status": "gagal", "message": f"body embedding tidak valid (maksimal {MAKS_TEKS} teks)"})
                return
            try:
                daftar_vektor = pembuat_embedding.buat(daftar_teks, jenis)
            except GalatLLM as galat:
                logging.error("embedding gagal: %s", galat)
                self.kirim_json(502, {"status": "gagal", "message": "layanan embedding sedang bermasalah"})
                return
            hasil = {"model": pembuat_embedding.model, "vektor": daftar_vektor}
            self.kirim_json(200, {"status": "sukses", "message": "embedding", "data": hasil})

        def jawab_stream(self, pilihan, data):
            """Mengirim jawaban sebagai Server-Sent Events: status langkah, potongan teks, lalu hasil akhir."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def kabar(jenis, isi):
                self.wfile.write(f"event: {jenis}\ndata: {json.dumps(isi, ensure_ascii=False)}\n\n".encode("utf-8"))

            try:
                hasil = pilihan.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"), kabar)
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