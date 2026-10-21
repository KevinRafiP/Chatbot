import random
from datetime import datetime, timedelta, timezone

from ingatan import pilih_ingatan
from pengaman.aturan import batas_sumber, butuh_cari, minta_cari_ulang, minta_internet, periksa_pertanyaan, permintaan_merusak, tanya_selera

MAKS_RIWAYAT = 10
# 4 pesan terakhir dikirim hampir utuh agar jawaban sebelumnya (beserta daftar sumbernya) terbaca lengkap
JUMLAH_PESAN_TERBARU = 4
MAKS_HURUF_TERBARU = 1000
MAKS_HURUF_LAMA = 1000

MAKS_KONTEKS = 10
# undian disiapkan untuk 2 sampai MAKS_PILIHAN pilihan, karena kode tidak tahu berapa pilihan yang disebut pengguna
MAKS_PILIHAN = 6

ZONA_WIB = timezone(timedelta(hours=7))


def buat_siapkan(kotak_alat):
    """Simpul pertama: memeriksa pertanyaan dan menyusun pesan untuk LLM."""

    def siapkan(keadaan):
        pertanyaan = periksa_pertanyaan(keadaan.get("pertanyaan"))
        keadaan["pertanyaan"] = pertanyaan
        keadaan["ditolak"] = permintaan_merusak(pertanyaan)
        if keadaan["ditolak"]:
            return keadaan

        segarkan = minta_cari_ulang(pertanyaan)
        selera = tanya_selera(pertanyaan)
        minimal, maksimal = batas_sumber(pertanyaan)
        pesan = susun_pesan(pertanyaan, keadaan.get("konteks"), minimal, maksimal,
                            pilih_ingatan(keadaan.get("ingatan"), pertanyaan, keadaan.get("riwayat")), selera)

        # alat internet selalu diberikan, karena data internal bisa cocok sebagian saja (misalnya hanya nama gamenya)
        keadaan["deklarasi"] = kotak_alat.deklarasi()
        # pertanyaan fakta wajib dicari dulu di putaran pertama jika tidak ada data internal yang cocok;
        # permintaan cari ulang selalu dicari, pertanyaan selera tidak perlu dicari
        perlu_cari = segarkan or (butuh_cari(pertanyaan) and not selera)
        langsung_cari = segarkan or minta_internet(pertanyaan) or not keadaan.get("konteks")
        keadaan["wajib_cari"] = langsung_cari and kotak_alat.wajib_cari(segarkan) and perlu_cari
        # jika ada data internal, model yang memutuskan; jawaban "tidak ada informasi" tanpa mencari diulang di simpul pikir
        keadaan["cari_cadangan"] = perlu_cari and not keadaan["wajib_cari"] and kotak_alat.wajib_cari(paksa=True)
        keadaan["isi"] = susun_isi(keadaan.get("riwayat"), pesan)
        keadaan["catatan"] = {
            "sumber": sumber_internal(keadaan.get("konteks")),
            "bukti": bukti_internal(keadaan.get("konteks")),
            "jumlah_baca": 0,
            "maks_sumber_luar": maksimal,
            "segarkan": segarkan,
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

def undian_pilihan():
    """Nomor pilihan yang diundi untuk tiap kemungkinan jumlah pilihan, agar jawaban selera tidak selalu sama."""
    return "; ".join(f"{n} pilihan: nomor {random.randint(1, n)}" for n in range(2, MAKS_PILIHAN + 1))

def susun_pesan(pertanyaan, konteks, minimal, maksimal, ingatan=None, selera=False):
    tanggal = f"Tanggal hari ini: {datetime.now(ZONA_WIB):%Y-%m-%d}"
    aturan_sumber = f"Sumber luar: paling banyak {maksimal}."
    if minimal:
        aturan_sumber = f"Sumber luar: minimal {minimal}, paling banyak {maksimal}."

    baris = [tanggal, aturan_sumber]
    if selera:
        baris.append(f"Undian pilihan: {undian_pilihan()}.")
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