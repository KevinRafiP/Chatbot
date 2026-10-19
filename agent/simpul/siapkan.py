from datetime import datetime, timedelta, timezone

from ingatan import pilih_ingatan
from pengaman.aturan import batas_sumber, butuh_cari, minta_internet, periksa_pertanyaan, permintaan_merusak

MAKS_RIWAYAT = 10
# 4 pesan terakhir dikirim hampir utuh agar jawaban sebelumnya (beserta daftar sumbernya) terbaca lengkap
JUMLAH_PESAN_TERBARU = 4
MAKS_HURUF_TERBARU = 5000
MAKS_HURUF_LAMA = 1000

MAKS_KONTEKS = 10

ZONA_WIB = timezone(timedelta(hours=7))


def buat_siapkan(kotak_alat):
    """Simpul pertama: memeriksa pertanyaan dan menyusun pesan untuk LLM."""

    def siapkan(keadaan):
        pertanyaan = periksa_pertanyaan(keadaan.get("pertanyaan"))
        keadaan["pertanyaan"] = pertanyaan
        keadaan["ditolak"] = permintaan_merusak(pertanyaan)
        if keadaan["ditolak"]:
            return keadaan

        boleh_internet = minta_internet(pertanyaan) or not keadaan.get("konteks")
        minimal, maksimal = batas_sumber(pertanyaan)
        pesan = susun_pesan(pertanyaan, keadaan.get("konteks"), minimal, maksimal, pilih_ingatan(keadaan.get("ingatan"), pertanyaan, keadaan.get("riwayat")))

        keadaan["deklarasi"] = kotak_alat.deklarasi() if boleh_internet else None
        # pertanyaan fakta wajib dicari dulu di putaran pertama, agar model tidak menjawab dari ingatannya sendiri
        keadaan["wajib_cari"] = bool(keadaan["deklarasi"]) and kotak_alat.wajib_cari() and butuh_cari(pertanyaan)
        keadaan["isi"] = susun_isi(keadaan.get("riwayat"), pesan)
        keadaan["catatan"] = {
            "sumber": sumber_internal(keadaan.get("konteks")),
            "bukti": bukti_internal(keadaan.get("konteks")),
            "jumlah_baca": 0,
            "maks_sumber_luar": maksimal,
        }
        keadaan["putaran_llm"] = 0
        return keadaan

    return siapkan


def susun_isi(riwayat, pesan_baru):
    """Menyusun riwayat dan pesan baru menjadi giliran user/assistant yang selalu bergantian, diawali user."""
    daftar = []
    terpilih = (riwayat or [])[-MAKS_RIWAYAT:]
    for urutan, pesan in enumerate(terpilih):
        teks = str(pesan.get("teks", "")).strip()
        if teks:
            peran = "assistant" if pesan.get("peran") == "asisten" else "user"
            batas = MAKS_HURUF_TERBARU if urutan >= len(terpilih) - JUMLAH_PESAN_TERBARU else MAKS_HURUF_LAMA
            daftar.append((peran, teks[:batas]))
    daftar.append(("user", pesan_baru))

    hasil = []
    for peran, teks in daftar:
        if not hasil and peran == "assistant":
            continue
        if hasil and hasil[-1]["role"] == peran:
            hasil[-1]["content"][0]["text"] += "\n\n" + teks
        else:
            hasil.append({"role": peran, "content": [{"text": teks}]})
    return hasil


def sumber_internal(konteks):
    """Mendaftarkan data internal sebagai sumber nomor 1, 2, dst. sesuai urutannya di pesan."""
    return [{"judul": str(item.get("judul", "")), "url": ""} for item in (konteks or [])[:MAKS_KONTEKS]]

def bukti_internal(konteks):
    """Isi data internal disimpan per nomor agar bisa dipakai saat verifikasi jawaban."""
    return {
        i: {"tingkat": "internal", "isi": str(item.get("isi", ""))[:3000]}
        for i, item in enumerate((konteks or [])[:MAKS_KONTEKS], start=1)
    }

def susun_pesan(pertanyaan, konteks, minimal, maksimal, ingatan=None):
    tanggal = f"Tanggal hari ini: {datetime.now(ZONA_WIB):%Y-%m-%d}"
    aturan_sumber = f"Sumber luar: paling banyak {maksimal}."
    if minimal:
        aturan_sumber = f"Sumber luar: minimal {minimal}, paling banyak {maksimal}."

    baris = [tanggal, aturan_sumber]
    if ingatan:
        baris.append(f"Ingatan tentang pengguna:\n{ingatan}")
    if not konteks:
        baris.append("Data internal: (tidak ada data yang cocok)")
    else:
        baris.append("Data internal:")
        for i, item in enumerate(konteks[:MAKS_KONTEKS], start=1):
            baris.append(f"[{i}] {item.get('judul', '')}\n{item.get('isi', '')}")
    baris.append(f"Pertanyaan: {pertanyaan}")
    return "\n\n".join(baris)