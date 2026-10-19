import logging
import re

from llm.client import GalatLLM
from prompt import INSTRUKSI_VERIFIKASI
from simpul.akhir import bersihkan_format

# hasil verifikasi yang jauh lebih pendek dari draf dianggap rusak, jadi draf yang dipakai
RASIO_MINIMAL = 0.3
# jawaban verifikasi jika draf tidak perlu diubah; draf langsung dipakai tanpa ditulis ulang
TANDA_SESUAI = "SESUAI"

MAKS_HURUF_PERCAKAPAN = 5000

POLA_PEMBUKA = re.compile(r"\A\s*(berikut|ini adalah|jawaban (yang )?(sudah )?diperbaiki)[^\n]*:\s*\n", re.IGNORECASE)


def buat_verifikasi(klien):
    """Simpul yang memeriksa draf jawaban terhadap isi sumbernya, hanya jika jawaban memakai internet."""

    def verifikasi(keadaan):
        catatan = keadaan["catatan"]
        if not any(sumber["url"] for sumber in catatan["sumber"]):
            return keadaan

        bagian = keadaan["konten_terakhir"].get("content", [])
        draf = bersihkan_format("".join(b.get("text", "") for b in bagian))
        if not draf:
            return keadaan
        if keadaan.get("kabar"):
            keadaan["kabar"]("status", {"teks": "Memeriksa sumber"})

        isi = susun_bahan(keadaan["pertanyaan"], draf, catatan, keadaan.get("riwayat"))
        try:
            konten = klien.kirim(INSTRUKSI_VERIFIKASI, [{"role": "user", "content": [{"text": isi}]}], None)
        except GalatLLM as galat:
            logging.warning("verifikasi jawaban gagal, draf dipakai apa adanya: %s", galat)
            return keadaan

        baru = "".join(b.get("text", "") for b in konten.get("content", []) if "text" in b)
        baru = POLA_PEMBUKA.sub("", bersihkan_format(baru)).strip()
        if baru.upper().strip(" .") == TANDA_SESUAI:
            return keadaan
        if len(baru) < len(draf) * RASIO_MINIMAL:
            logging.warning("hasil verifikasi terlalu pendek, draf dipakai apa adanya")
            return keadaan

        keadaan["konten_terakhir"] = {"role": "assistant", "content": [{"text": baru}]}
        return keadaan

    return verifikasi


def susun_bahan(pertanyaan, draf, catatan, riwayat=None):
    """Menyusun percakapan sebelumnya, pertanyaan, daftar sumber beserta tingkat dan isinya, lalu draf jawaban."""
    baris = []
    sebelumnya = [p for p in (riwayat or [])[-2:] if isinstance(p, dict) and str(p.get("teks", "")).strip()]
    if sebelumnya:
        baris.append("Percakapan sebelumnya:")
        for pesan in sebelumnya:
            nama = "Asisten" if pesan.get("peran") == "asisten" else "Pengguna"
            baris.append(f"{nama}: {str(pesan['teks']).strip()[:MAKS_HURUF_PERCAKAPAN]}")
    baris += [f"Pertanyaan pengguna: {pertanyaan}", "Daftar sumber:"]
    for nomor, sumber in enumerate(catatan["sumber"], start=1):
        bukti = catatan["bukti"].get(nomor, {})
        alamat = sumber["url"] or "data internal"
        baris.append(
            f"[{nomor}] tingkat {bukti.get('tingkat', 'sedang')} | {sumber['judul']} | {alamat}\n"
            f"{bukti.get('isi') or '(isi tidak tersedia)'}"
        )
    baris.append(f"Draf jawaban:\n{draf}")
    return "\n\n".join(baris)
