import json

from llm.client import GalatLLM, buka, kirim_json


class KlienAPI:
    def __init__(self, alamat, api_key, model, batas_waktu=60):
        self.alamat = alamat.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batas_waktu = batas_waktu

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None, wajib_alat=False, saat_teks=None):
        """Mengirim percakapan ke layanan berformat OpenAI (chat/completions) dan mengembalikan pesan balasan model.
        Jika saat_teks diisi, balasan diminta sebagai stream dan saat_teks(potongan) dipanggil setiap ada teks baru."""
        pesan = [{"role": "system", "content": instruksi_sistem}]
        for giliran in isi_percakapan:
            pesan.extend(ke_format_api(giliran))

        badan = {"model": self.model, "messages": pesan}
        if deklarasi_alat:
            badan["tools"] = [{"type": "function", "function": d} for d in deklarasi_alat]
            if wajib_alat:
                badan["tool_choice"] = "required"

        header = {"Content-Type": "application/json"}
        if self.api_key:
            header["Authorization"] = f"Bearer {self.api_key}"
        alamat = f"{self.alamat}/chat/completions"
        if saat_teks:
            badan["stream"] = True
            with buka(alamat, json.dumps(badan).encode("utf-8"), header, self.batas_waktu, "Layanan LLM") as respon:
                balasan, alasan = rakit_pesan_stream(respon, saat_teks)
            pemakaian = None
        else:
            data = kirim_json(alamat, json.dumps(badan).encode("utf-8"), header, self.batas_waktu, "Layanan LLM")
            pilihan = data.get("choices") or []
            if not pilihan or not pilihan[0].get("message"):
                raise GalatLLM("Layanan LLM tidak memberi jawaban")
            balasan, alasan, pemakaian = pilihan[0]["message"], pilihan[0].get("finish_reason"), data.get("usage")
        try:
            return dari_format_api(balasan)
        except GalatLLM as galat:
            # info tambahan untuk melacak balasan kosong, misalnya prompt terpotong karena konteks model penuh
            raise GalatLLM(f"{galat} (finish_reason={alasan}, usage={pemakaian})", galat.kode)

def rakit_pesan_stream(respon, saat_teks):
    """Menyusun kembali pesan utuh dari baris "data: {...}" stream format OpenAI, sambil meneruskan teksnya."""
    teks, panggilan, alasan = "", {}, None
    for baris in respon:
        baris = baris.decode("utf-8", "replace").strip()
        if not baris.startswith("data:"):
            continue
        isi = baris[5:].strip()
        if isi == "[DONE]":
            break
        try:
            data = json.loads(isi)
        except ValueError:
            continue
        if data.get("error"):
            raise GalatLLM(f"Layanan LLM menghentikan stream: {str(data['error'])[:300]}")

        for pilihan in data.get("choices") or []:
            delta = pilihan.get("delta") or {}
            if delta.get("content"):
                teks += delta["content"]
                saat_teks(delta["content"])
            for potongan in delta.get("tool_calls") or []:
                tujuan = panggilan.setdefault(potongan.get("index", 0),
                                              {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if potongan.get("id"):
                    tujuan["id"] = potongan["id"]
                fungsi = potongan.get("function") or {}
                tujuan["function"]["name"] += fungsi.get("name") or ""
                tujuan["function"]["arguments"] += fungsi.get("arguments") or ""
            alasan = pilihan.get("finish_reason") or alasan

    pesan = {"role": "assistant", "content": teks or None}
    if panggilan:
        pesan["tool_calls"] = [panggilan[nomor] for nomor in sorted(panggilan)]
    return pesan, alasan

def ke_format_api(giliran):
    """Mengubah satu giliran berbentuk internal (content berisi text/toolUse/toolResult) ke pesan format OpenAI."""
    isi = giliran.get("content", [])
    hasil_alat = [b["toolResult"] for b in isi if "toolResult" in b]
    teks = "".join(b.get("text", "") for b in isi)
    if hasil_alat:
        pesan = [{"role": "tool", "tool_call_id": h["toolUseId"], "content": h["content"][0]["text"]}
                 for h in hasil_alat]
        if teks:
            pesan.append({"role": "user", "content": teks})
        return pesan

    pesan = {"role": giliran.get("role", "user"), "content": teks or None}
    panggilan = [b["toolUse"]["asli"] for b in isi if "toolUse" in b]
    if panggilan:
        pesan["tool_calls"] = panggilan
    return [pesan]


def dari_format_api(pesan):
    """Mengubah pesan balasan format OpenAI ke bentuk internal yang dipakai simpul."""
    isi = []
    if pesan.get("content"):
        isi.append({"text": pesan["content"]})

    for panggilan in pesan.get("tool_calls") or []:
        fungsi = panggilan.get("function") or {}
        try:
            argumen = json.loads(fungsi.get("arguments") or "{}")
        except ValueError:
            argumen = {}
        isi.append({
            "toolUse": {
                "toolUseId": panggilan.get("id", ""),
                "name": fungsi.get("name", ""),
                "input": argumen if isinstance(argumen, dict) else {},
                "asli": panggilan,
            }
        })

    if not isi:
        raise GalatLLM("Layanan LLM mengirim jawaban kosong", 204)
    return {"role": "assistant", "content": isi}