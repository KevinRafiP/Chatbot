"""Mengirim log ERROR ke Sentry lewat API envelope tanpa SDK, jadi tidak menambah dependensi."""
import json
import logging
import re
import socket
import threading
import time
import traceback
import urllib.request
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

JEDA_SAMA = 600
MAKS_PER_JAM = 60
PANJANG_MAKS = 4000
POLA_ANGKA = re.compile(r"[0-9a-f]{8}-[0-9a-f-]{27}|\d+")


class PelaporSentry(logging.Handler):
    def __init__(self, dsn, lingkungan="", layanan="agent"):
        super().__init__(level=logging.ERROR)
        alamat = urlparse(dsn.strip())
        bagian = alamat.path.strip("/").split("/")
        if not alamat.username or not alamat.hostname or not bagian[-1]:
            raise ValueError("SENTRY_DSN tidak valid")
        awalan = "/".join(bagian[:-1])
        self.alamat = f"{alamat.scheme}://{alamat.netloc.split('@')[-1]}{'/' + awalan if awalan else ''}/api/{bagian[-1]}/envelope/"
        self.kunci = alamat.username
        self.dsn = dsn.strip()
        self.host = alamat.hostname
        self.lingkungan = lingkungan or "production"
        self.layanan = layanan
        self.kunci_kirim = threading.Lock()
        self.terakhir = {}
        self.awal_jam = 0.0
        self.jumlah_jam = 0

    def boleh_kirim(self, sidik):
        with self.kunci_kirim:
            sekarang = time.monotonic()
            if sekarang - self.terakhir.get(sidik, -JEDA_SAMA) < JEDA_SAMA:
                return False
            if sekarang - self.awal_jam >= 3600:
                self.awal_jam, self.jumlah_jam = sekarang, 0
                self.terakhir = {k: t for k, t in self.terakhir.items() if sekarang - t < JEDA_SAMA}
            if self.jumlah_jam >= MAKS_PER_JAM:
                return False
            self.jumlah_jam += 1
            self.terakhir[sidik] = sekarang
            return True

    def emit(self, catatan):
        try:
            pesan = catatan.getMessage()[:PANJANG_MAKS]
            sidik = POLA_ANGKA.sub("#", pesan)[:200]
            if not self.boleh_kirim(sidik):
                return
            kejadian = self.kejadian(catatan, pesan, sidik)
            threading.Thread(target=self.kirim, args=(kejadian,), daemon=True).start()
        except Exception:
            pass

    def kejadian(self, catatan, pesan, sidik):
        waktu = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        isi = {
            "event_id": uuid.uuid4().hex, "timestamp": waktu, "platform": "python", "level": "error",
            "logger": catatan.name, "server_name": socket.gethostname(), "environment": self.lingkungan,
            "message": {"formatted": pesan}, "tags": {"layanan": self.layanan}, "fingerprint": [self.layanan, sidik],
        }
        if catatan.exc_info and catatan.exc_info[0]:
            jenis, nilai, jejak = catatan.exc_info
            bingkai = [{"filename": b.filename.rsplit("/", 1)[-1], "function": b.name, "lineno": b.lineno, "context_line": b.line}
                       for b in traceback.extract_tb(jejak)[-30:]]
            isi["exception"] = {"values": [{"type": jenis.__name__, "value": str(nilai)[:PANJANG_MAKS],
                                            "stacktrace": {"frames": bingkai}}]}
            isi["fingerprint"].append(jenis.__name__)
        return isi

    def kirim(self, isi):
        kepala = json.dumps({"event_id": isi["event_id"], "sent_at": isi["timestamp"], "dsn": self.dsn})
        badan = f"{kepala}\n{{\"type\":\"event\"}}\n{json.dumps(isi, ensure_ascii=False, default=str)}\n".encode()
        permintaan = urllib.request.Request(self.alamat, data=badan, method="POST", headers={
            "Content-Type": "application/x-sentry-envelope",
            "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_client=vokapas/1.0, sentry_key={self.kunci}",
        })
        try:
            with urllib.request.urlopen(permintaan, timeout=5) as respon:
                respon.read(4096)
        except Exception:
            pass


def pasang_pelapor(dsn, lingkungan=""):
    """Memasang pelapor ke logger utama; mengembalikan keterangan untuk tabel saat menyala."""
    if not dsn:
        return "mati"
    try:
        pelapor = PelaporSentry(dsn, lingkungan)
    except ValueError as galat:
        return f"mati, {galat}"
    logging.getLogger().addHandler(pelapor)
    return f"aktif, Sentry ({pelapor.host})"
