import threading

# setiap permintaan HTTP di agent berjalan di benangnya sendiri, jadi catatan token disimpan per benang
_lokal = threading.local()


def mulai():
    """Mengosongkan catatan pemakaian sebelum satu jawaban dibuat."""
    _lokal.catatan = {"token_masuk": 0, "token_keluar": 0, "panggilan_llm": 0}


def catat(masuk, keluar):
    """Menambah token satu panggilan LLM; diabaikan jika mulai() belum dipanggil di benang ini."""
    catatan = getattr(_lokal, "catatan", None)
    if catatan is None:
        return
    catatan["token_masuk"] += int(masuk or 0)
    catatan["token_keluar"] += int(keluar or 0)
    catatan["panggilan_llm"] += 1


def ambil():
    return dict(getattr(_lokal, "catatan", None) or {"token_masuk": 0, "token_keluar": 0, "panggilan_llm": 0})
