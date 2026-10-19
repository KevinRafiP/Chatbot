import json
import struct
import urllib.parse

from llm.client import GalatLLM, buka, kirim_json
from llm.tanda_tangan import tanda_tangani

MAKS_TOKEN_JAWABAN = 1024


class KlienAWS:
    def __init__(self, access_key, secret_key, wilayah, model, batas_waktu=60):
        self.access_key = access_key
        self.secret_key = secret_key
        self.wilayah = wilayah
        self.model = model
        self.batas_waktu = batas_waktu
        self.alamat = f"https://bedrock-runtime.{wilayah}.amazonaws.com"

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None, wajib_alat=False, saat_teks=None):
        """Mengirim percakapan ke Amazon Bedrock (Converse) dan mengembalikan pesan balasan model.
        Jika saat_teks diisi, dipakai ConverseStream dan saat_teks(potongan) dipanggil setiap ada teks baru."""
        badan = {
            "system": [{"text": instruksi_sistem}],
            "messages": isi_percakapan,
            "inferenceConfig": {"maxTokens": MAKS_TOKEN_JAWABAN},
        }
        if deklarasi_alat:
            badan["toolConfig"] = {"tools": [ubah_alat(d) for d in deklarasi_alat]}
            if wajib_alat:
                badan["toolConfig"]["toolChoice"] = {"any": {}}

        jalur = "converse-stream" if saat_teks else "converse"
        alamat = f"{self.alamat}/model/{urllib.parse.quote(self.model, safe='')}/{jalur}"
        data_kirim = json.dumps(badan).encode("utf-8")
        header = tanda_tangani("POST", alamat, data_kirim, self.wilayah, "bedrock",
                               self.access_key, self.secret_key, {"Content-Type": "application/json"})
        if saat_teks:
            with buka(alamat, data_kirim, header, self.batas_waktu, "Bedrock") as respon:
                pesan, alasan = rakit_pesan_stream(respon, saat_teks)
        else:
            data = kirim_json(alamat, data_kirim, header, self.batas_waktu, "Bedrock")
            pesan, alasan = (data.get("output") or {}).get("message"), data.get("stopReason")

        if not pesan or not pesan.get("content"):
            raise GalatLLM(f"Bedrock tidak memberi jawaban (alasan berhenti: {alasan})")
        return pesan

def rakit_pesan_stream(respon, saat_teks):
    """Menyusun kembali pesan utuh (teks dan toolUse) dari event ConverseStream, sambil meneruskan teksnya."""
    blok = {}
    alasan = None
    for header, isi in baca_event_aws(respon):
        data = json.loads(isi or b"{}")
        if header.get(":message-type") != "event":
            raise GalatLLM(f"Bedrock menghentikan stream ({header.get(':exception-type')}): {str(data.get('message', ''))[:300]}")

        jenis = header.get(":event-type")
        nomor = data.get("contentBlockIndex", 0)
        if jenis == "contentBlockStart" and "toolUse" in data.get("start", {}):
            blok[nomor] = {"toolUse": {**data["start"]["toolUse"], "input": ""}}
        elif jenis == "contentBlockDelta":
            delta = data.get("delta", {})
            if "text" in delta:
                blok.setdefault(nomor, {"text": ""})["text"] += delta["text"]
                saat_teks(delta["text"])
            elif "toolUse" in delta and "toolUse" in blok.get(nomor, {}):
                blok[nomor]["toolUse"]["input"] += delta["toolUse"].get("input", "")
        elif jenis == "messageStop":
            alasan = data.get("stopReason")

    konten = []
    for nomor in sorted(blok):
        isi_blok = blok[nomor]
        if "toolUse" in isi_blok:
            try:
                isi_blok["toolUse"]["input"] = json.loads(isi_blok["toolUse"]["input"] or "{}")
            except ValueError:
                isi_blok["toolUse"]["input"] = {}
            konten.append(isi_blok)
        elif isi_blok["text"].strip():
            konten.append(isi_blok)
    return {"role": "assistant", "content": konten}, alasan


# panjang nilai header AWS event stream menurut kode jenisnya; jenis 6 (bytes) dan 7 (string) diawali panjang 2 byte
UKURAN_HEADER = {0: 0, 1: 0, 2: 1, 3: 2, 4: 4, 5: 8, 8: 8, 9: 16}


def baca_event_aws(respon):
    """Membaca event biner AWS event stream satu per satu: 4 byte panjang total, 4 byte panjang header,
    4 byte CRC, header, isi JSON, lalu 4 byte CRC. CRC tidak diperiksa karena koneksi sudah dijaga HTTPS."""
    while True:
        awal = baca_pas(respon, 12)
        if not awal:
            return
        panjang_total, panjang_header = struct.unpack(">II", awal[:8])
        sisa = baca_pas(respon, panjang_total - 12)
        yield urai_header(sisa[:panjang_header]), sisa[panjang_header:-4]


def baca_pas(respon, jumlah):
    """Membaca tepat sejumlah byte; kosong jika stream sudah habis."""
    data = b""
    while len(data) < jumlah:
        potongan = respon.read(jumlah - len(data))
        if not potongan:
            if data:
                raise GalatLLM("stream Bedrock terputus di tengah event")
            return b""
        data += potongan
    return data


def urai_header(data):
    header, i = {}, 0
    while i < len(data):
        panjang_nama = data[i]
        nama = data[i + 1:i + 1 + panjang_nama].decode("utf-8")
        i += 1 + panjang_nama
        jenis = data[i]
        i += 1
        if jenis in (6, 7):
            panjang = struct.unpack(">H", data[i:i + 2])[0]
            nilai = data[i + 2:i + 2 + panjang]
            i += 2 + panjang
            header[nama] = nilai.decode("utf-8") if jenis == 7 else nilai
        else:
            header[nama] = data[i:i + UKURAN_HEADER[jenis]]
            i += UKURAN_HEADER[jenis]
    return header

def ubah_alat(deklarasi):
    """Mengubah deklarasi alat milik agent ke bentuk toolSpec yang diminta Bedrock."""
    return {
        "toolSpec": {
            "name": deklarasi["name"],
            "description": deklarasi["description"],
            "inputSchema": {"json": deklarasi["parameters"]},
        }
    }