from pengaman.aturan import minta_internet, periksa_pertanyaan

MAKS_RIWAYAT = 10


def buat_siapkan(kotak_alat):
    """Simpul pertama: memeriksa pertanyaan dan menyusun pesan untuk LLM."""

    def siapkan(keadaan):
        pertanyaan = periksa_pertanyaan(keadaan.get("pertanyaan"))
        boleh_internet = minta_internet(pertanyaan)

        keadaan["pertanyaan"] = pertanyaan
        keadaan["deklarasi"] = kotak_alat.deklarasi() if boleh_internet else None
        keadaan["isi"] = susun_riwayat(keadaan.get("riwayat")) + [
            {"role": "user", "parts": [{"text": susun_pesan(pertanyaan, keadaan.get("konteks"))}]}
        ]
        keadaan["catatan"] = {"sumber": [], "jumlah_baca": 0}
        keadaan["putaran_llm"] = 0
        return keadaan

    return siapkan


def susun_riwayat(riwayat):
    hasil = []
    for pesan in (riwayat or [])[-MAKS_RIWAYAT:]:
        teks = str(pesan.get("teks", "")).strip()
        if not teks:
            continue
        peran = "model" if pesan.get("peran") == "asisten" else "user"
        hasil.append({"role": peran, "parts": [{"text": teks[:2000]}]})
    return hasil


def susun_pesan(pertanyaan, konteks):
    if not konteks:
        return f"Data internal: (tidak ada data yang cocok)\n\nPertanyaan: {pertanyaan}"

    baris = ["Data internal:"]
    for i, item in enumerate(konteks[:5], start=1):
        baris.append(f"[{i}] {item.get('judul', '')}\n{item.get('isi', '')}")
    baris.append(f"\nPertanyaan: {pertanyaan}")
    return "\n\n".join(baris)