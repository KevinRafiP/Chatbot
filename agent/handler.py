import base64
import binascii
import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler

from alat.berkas import baca_berkas
from alat.jaringan import GalatAlat
from alat.kode import terima_hasil
from llm import denyut
from llm.client import GalatLLM
from llm.embedding import MAKS_TEKS
from pengaman.aturan import GalatPengaman

BATAS_BODY = 256_000
# berkas dikirim sebagai base64, jadi ukurannya sekitar 4/3 dari berkas aslinya
BATAS_BODY_BERKAS = 8_000_000


def buat_penangan(daftar_agen, api_key, pembuat_embedding=None, maks_huruf_berkas=20000, pembaca_gambar=None, cek_llm=None):
    """Membuat kelas penangan HTTP yang sudah membawa agen per profil (mendalam, cepat, tamu) dan API key."""
    agen = daftar_agen["mendalam"]

    class Penangan(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/kesehatan":
                # llm = apakah model AI bisa dihubungi (misalnya laptop untuk mode lokal sedang menyala)
                data = {"llm": cek_llm()} if cek_llm else {}
                self.kirim_json(200, {"status": "sukses", "message": "layanan agent aktif", "data": data})
                return
            self.kirim_json(404, {"status": "gagal", "message": "alamat tidak ditemukan"})

        def do_POST(self):
            if self.path not in ("/jawab", "/jawab-stream", "/ringkas", "/ringkas-percakapan", "/embed", "/embed-info", "/baca-berkas",
                                 "/hasil-kode"):
                self.kirim_json(404, {"status": "gagal", "message": "alamat tidak ditemukan"})
                return

            if not hmac.compare_digest(self.headers.get("X-API-Key", ""), api_key):
                self.kirim_json(401, {"status": "gagal", "message": "API key tidak valid"})
                return

            panjang = int(self.headers.get("Content-Length") or 0)
            if panjang <= 0 or panjang > (BATAS_BODY_BERKAS if self.path == "/baca-berkas" else BATAS_BODY):
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
            if self.path == "/hasil-kode":
                # hasil jalankan_python dari browser pengguna, diteruskan backend; id hanya dikenal browser yang menerima kodenya
                if terima_hasil(data.get("id"), data):
                    self.kirim_json(200, {"status": "sukses", "message": "hasil kode diterima", "data": {}})
                else:
                    self.kirim_json(404, {"status": "gagal", "message": "kode ini tidak sedang ditunggu"})
                return
            if self.path == "/baca-berkas":
                self.baca_berkas(data)
                return
            # profil dipilih backend: "tamu", "cepat", atau "mendalam" (bawaan)
            pilihan = daftar_agen.get(str(data.get("profil")), agen)
            if self.path == "/jawab-stream":
                self.jawab_stream(pilihan, data)
                return
            try:
                if self.path == "/ringkas":
                    hasil = {"ingatan": agen.ringkas(data.get("ingatan"), data.get("riwayat"))}
                elif self.path == "/ringkas-percakapan":
                    hasil = agen.ringkas_percakapan(data.get("ringkasan"), data.get("riwayat"))
                else:
                    hasil = pilihan.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"),
                                          lampiran=data.get("lampiran"), bisa_email=data.get("bisa_email"),
                                          ringkasan=data.get("ringkasan"))
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
        
        def baca_berkas(self, data):
            """Mengambil teks dari berkas unggahan atau foto; body {"nama": "laporan.pdf", "isi": "base64"}."""
            try:
                isi = base64.b64decode(str(data.get("isi", "")), validate=True)
                hasil = baca_berkas(data.get("nama"), isi, maks_huruf_berkas, pembaca_gambar)
            except (binascii.Error, ValueError):
                self.kirim_json(400, {"status": "gagal", "message": "isi berkas tidak valid"})
                return
            except GalatAlat as galat:
                self.kirim_json(400, {"status": "gagal", "message": str(galat)})
                return
            except Exception:
                logging.exception("gagal membaca berkas")
                self.kirim_json(400, {"status": "gagal", "message": "berkas tidak bisa dibaca"})
                return
            self.kirim_json(200, {"status": "sukses", "message": "isi berkas", "data": hasil})

        def jawab_stream(self, pilihan, data):
            """Mengirim jawaban sebagai Server-Sent Events: status langkah, potongan teks, lalu hasil akhir."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            def kabar(jenis, isi):
                self.wfile.write(f"event: {jenis}\ndata: {json.dumps(isi, ensure_ascii=False)}\n\n".encode("utf-8"))

            # baris komentar SSE (diawali ":") diabaikan backend; gunanya hanya mengetahui koneksi yang sudah putus
            denyut.pasang(lambda: self.wfile.write(b": denyut\n\n"))
            try:
                hasil = pilihan.jawab(data.get("pertanyaan", ""), data.get("konteks"), data.get("riwayat"), data.get("ingatan"), kabar,
                                      data.get("lampiran"), data.get("bisa_email"), data.get("ringkasan"))
                kabar("selesai", hasil)
            except (BrokenPipeError, ConnectionResetError, denyut.Dihentikan):
                logging.info("backend menutup stream sebelum jawaban selesai (dihentikan pengguna)")
            except GalatPengaman as galat:
                kabar("galat", {"message": str(galat)})
            except GalatLLM as galat:
                logging.error("LLM gagal: %s", galat)
                kabar("galat", {"message": "layanan AI sedang bermasalah"})
            except Exception:
                logging.exception("galat tak terduga")
                kabar("galat", {"message": "agent sedang bermasalah"})
            finally:
                denyut.lepas()

        def kirim_json(self, status, data):
            badan = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(badan)))
            self.end_headers()
            self.wfile.write(badan)

    return Penangan