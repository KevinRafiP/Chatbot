from datetime import datetime, timedelta, timezone

from pengaman.aturan import minta_internet, periksa_pertanyaan

MAKS_RIWAYAT = 10

MAKS_KONTEKS = 10

ZONA_WIB = timezone(timedelta(hours=7))


def buat_siapkan(kotak_alat):
    """Simpul pertama: memeriksa pertanyaan dan menyusun pesan untuk LLM."""

    def siapkan(keadaan):
        pertanyaan = periksa_pertanyaan(keadaan.get("pertanyaan"))
        boleh_internet = minta_internet(pertanyaan) or not keadaan.get("konteks")

        keadaan["pertanyaan"] = pertanyaan
        keadaan["deklarasi"] = kotak_alat.deklarasi() if boleh_internet else None
        keadaan["isi"] = susun_isi(keadaan.get("riwayat"), susun_pesan(pertanyaan, keadaan.get("konteks")))
        keadaan["catatan"] = {"sumber": sumber_internal(keadaan.get("konteks")), "jumlah_baca": 0}
        keadaan["putaran_llm"] = 0
        return keadaan

    return siapkan


def susun_isi(riwayat, pesan_baru):
    """Menyusun riwayat dan pesan baru menjadi giliran user/assistant yang selalu bergantian, diawali user."""
    daftar = []
    for pesan in (riwayat or [])[-MAKS_RIWAYAT:]:
        teks = str(pesan.get("teks", "")).strip()
        if teks:
            peran = "assistant" if pesan.get("peran") == "asisten" else "user"
            daftar.append((peran, teks[:2000]))
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

def susun_pesan(pertanyaan, konteks):
    tanggal = f"Tanggal hari ini: {datetime.now(ZONA_WIB):%Y-%m-%d}"
    if not konteks:
        return f"{tanggal}\n\nData internal: (tidak ada data yang cocok)\n\nPertanyaan: {pertanyaan}"

    baris = [tanggal, "Data internal:"]
    for i, item in enumerate(konteks[:5], start=1):
        baris.append(f"[{i}] {item.get('judul', '')}\n{item.get('isi', '')}")
    baris.append(f"\nPertanyaan: {pertanyaan}")
    return "\n\n".join(baris)