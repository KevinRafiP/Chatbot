import json
import logging


def buat_aksi(kotak_alat):
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

        keadaan["isi"].append({"role": "user", "content": balasan})
        return keadaan

    return aksi