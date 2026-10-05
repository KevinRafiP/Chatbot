import logging


def buat_aksi(kotak_alat):
    """Simpul yang menjalankan alat yang diminta LLM lalu menyimpan hasilnya ke percakapan."""

    def aksi(keadaan):
        balasan = []
        for p in keadaan["panggilan"]:
            logging.info("agen memanggil alat %s", p.get("name"))
            # memanggil alat
            hasil = kotak_alat.jalankan(p.get("name", ""), p.get("args") or {}, keadaan["catatan"])
            respon = {"name": p.get("name", ""), "response": hasil}
            if "id" in p:
                respon["id"] = p["id"]
            balasan.append({"functionResponse": respon})

        keadaan["isi"].append({"role": "user", "parts": balasan})
        return keadaan

    return aksi