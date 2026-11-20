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
    lama = getattr(_lokal, "terakhir", (0, 0))
    _lokal.terakhir = (lama[0] + int(masuk or 0), lama[1] + int(keluar or 0))
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
    """Hanya token dan jumlah panggilan; kunci berawalan _ milik log harian tidak ikut dikirim ke backend."""
    catatan = getattr(_lokal, "catatan", None) or {}
    return {kunci: catatan.get(kunci, 0) for kunci in ("token_masuk", "token_keluar", "panggilan_llm")}


def ambil_terakhir():
    """Token panggilan LLM terakhir di benang ini (dipakai log harian), lalu dikosongkan."""
    terakhir = getattr(_lokal, "terakhir", (0, 0))
    _lokal.terakhir = (0, 0)
    return terakhir
