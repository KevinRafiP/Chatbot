import threading

# setiap permintaan HTTP di agent berjalan di benangnya sendiri, jadi catatan token disimpan per benang
_lokal = threading.local()
# alat yang berjalan bersamaan bisa memanggil model di benangnya sendiri, jadi penambahan dijaga gembok
_gembok = threading.Lock()


def mulai():
    """Mengosongkan catatan pemakaian sebelum satu jawaban dibuat."""
    _lokal.catatan = {"token_masuk": 0, "token_keluar": 0, "panggilan_llm": 0}


def catat(masuk, keluar):
    """Menambah token satu panggilan LLM; diabaikan jika mulai() belum dipanggil di benang ini."""
    catatan = getattr(_lokal, "catatan", None)
    if catatan is None:
        return
    with _gembok:
        catatan["token_masuk"] += int(masuk or 0)
        catatan["token_keluar"] += int(keluar or 0)
        catatan["panggilan_llm"] += 1


def bawa():
    """Catatan benang ini, untuk dipasang di benang pembantu agar token alat yang berjalan bersamaan ikut terhitung."""
    return getattr(_lokal, "catatan", None)


def pasang(catatan):
    _lokal.catatan = catatan


def ambil():
    return dict(getattr(_lokal, "catatan", None) or {"token_masuk": 0, "token_keluar": 0, "panggilan_llm": 0})
