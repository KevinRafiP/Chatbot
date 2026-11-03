import threading
import time

# jeda paling pendek antara dua tanda; koneksi yang putus ketahuan pada tanda kedua sesudahnya
JEDA_DETIK = 1.0

_lokal = threading.local()


class Dihentikan(Exception):
    """Koneksi ke backend sudah putus, misalnya pengguna menekan tombol berhenti."""


def pasang(kirim):
    """Dipanggil penangan stream sebelum menjawab; kirim() menulis tanda kecil ke koneksi backend."""
    _lokal.kirim = kirim
    _lokal.terakhir = 0.0


def lepas():
    _lokal.kirim = None


def detak():
    """Dipanggil di setiap event stream model. Paling sering sekali per JEDA_DETIK mengirim tanda ke backend,
    agar koneksi yang putus juga ketahuan saat model sedang berpikir dan belum menulis teks."""
    kirim = getattr(_lokal, "kirim", None)
    if kirim is None:
        return
    sekarang = time.monotonic()
    if sekarang - _lokal.terakhir < JEDA_DETIK:
        return
    _lokal.terakhir = sekarang
    try:
        kirim()
    except OSError as galat:
        raise Dihentikan() from galat