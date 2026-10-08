import json
import logging

PESAN_PUTARAN_TERAKHIR = (
    "Batas pencarian sudah tercapai. Jangan memanggil alat lagi. "
    "Jawab sekarang hanya dari informasi yang sudah terkumpul; "
    "jika belum cukup, katakan bagian mana yang tidak ditemukan."
)


def buat_aksi(kotak_alat, maks_langkah):
    """Simpul yang menjalankan alat yang diminta LLM lalu menyimpan hasilnya ke percakapan."""

    def aksi(keadaan):
        balasan = []
        for p in keadaan["panggilan"]:
            logging.info("agen memanggil alat %s", p.get("name"))
            hasil = kotak_alat.jalankan(p.get("name", ""), p.get("input") or {}, keadaan["catatan"])
            balasan.append({
                "toolResult": {
                    "toolUseId": p.get("toolUseId", ""),
                    "content": [{"text": json.dumps(hasil, ensure_ascii=False)}],
                }
            })

        if keadaan["putaran_llm"] >= maks_langkah - 1:
            balasan.append({"text": PESAN_PUTARAN_TERAKHIR})

        keadaan["isi"].append({"role": "user", "content": balasan})
        return keadaan

    return aksi