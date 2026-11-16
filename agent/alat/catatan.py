import threading


def kunci(catatan):
    """Gembok catatan satu jawaban; alat yang berjalan bersamaan mencatat sumber dan hitungan lewat gembok ini."""
    return catatan.setdefault("gembok", threading.RLock())
