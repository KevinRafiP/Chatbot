"""Menyusun keterangan saat agent menyala menjadi satu tabel rapi di terminal."""
import sys

LEBAR_GARIS = 64


def cetak_tabel(judul, baris):
    """baris berisi pasangan (label, nilai); ditulis sekaligus agar tidak tersela log lain."""
    panjang = max((len(label) for label, _ in baris), default=0)
    isi = ["", "=" * LEBAR_GARIS, f"  {judul.upper()}", "-" * LEBAR_GARIS]
    isi += [f"  {label.ljust(panjang)} : {nilai}" for label, nilai in baris]
    isi.append("=" * LEBAR_GARIS)
    sys.stderr.write("\n".join(isi) + "\n")
    sys.stderr.flush()


def aktif_mati(aktif, keterangan=""):
    """Menulis "aktif" atau "mati", ditambah keterangan bila ada."""
    kata = "aktif" if aktif else "mati"
    return f"{kata}, {keterangan}" if keterangan else kata
