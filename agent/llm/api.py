import json

from llm.client import GalatLLM, kirim_json


class KlienAPI:
    def __init__(self, alamat, api_key, model, batas_waktu=60):
        self.alamat = alamat.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batas_waktu = batas_waktu

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None):
        """Mengirim percakapan ke layanan berformat OpenAI (chat/completions) dan mengembalikan pesan balasan model."""
        pesan = [{"role": "system", "content": instruksi_sistem}]
        for giliran in isi_percakapan:
            pesan.extend(ke_format_api(giliran))

        badan = {"model": self.model, "messages": pesan}
        if deklarasi_alat:
            badan["tools"] = [{"type": "function", "function": d} for d in deklarasi_alat]

        header = {"Content-Type": "application/json"}
        if self.api_key:
            header["Authorization"] = f"Bearer {self.api_key}"
        data = kirim_json(f"{self.alamat}/chat/completions", json.dumps(badan).encode("utf-8"),
                          header, self.batas_waktu, "Layanan LLM")

        pilihan = data.get("choices") or []
        if not pilihan or not pilihan[0].get("message"):
            raise GalatLLM("Layanan LLM tidak memberi jawaban")
        return dari_format_api(pilihan[0]["message"])


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

    pesan = {"role": "assistant", "content": teks or None}
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
        raise GalatLLM("Layanan LLM mengirim jawaban kosong")
    return {"role": "assistant", "content": isi}