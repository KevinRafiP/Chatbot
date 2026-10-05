import json
import urllib.error
import urllib.request

ALAMAT_DASAR = "https://generativelanguage.googleapis.com/v1beta"


class GalatLLM(Exception):
    pass


class Klien:
    def __init__(self, api_key, model, batas_waktu=60):
        self.api_key = api_key
        self.model = model
        self.batas_waktu = batas_waktu

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None):
        """Mengirim percakapan ke Gemini dan mengembalikan content dari kandidat pertama."""
        badan = {
            "systemInstruction": {"parts": [{"text": instruksi_sistem}]},
            "contents": isi_percakapan,
        }
        if deklarasi_alat:
            badan["tools"] = [{"functionDeclarations": deklarasi_alat}]

        permintaan = urllib.request.Request(
            f"{ALAMAT_DASAR}/models/{self.model}:generateContent",
            data=json.dumps(badan).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )

        try:
            with urllib.request.urlopen(permintaan, timeout=self.batas_waktu) as respon:
                data = json.load(respon)
        except urllib.error.HTTPError as galat:
            detail = galat.read().decode("utf-8", "replace")[:300]
            raise GalatLLM(f"Gemini menolak ({galat.code}): {detail}")
        except (urllib.error.URLError, TimeoutError) as galat:
            raise GalatLLM(f"Gemini tidak bisa dihubungi: {galat}")

        kandidat = data.get("candidates") or []
        if not kandidat or "content" not in kandidat[0]:
            raise GalatLLM("Gemini tidak memberi jawaban (bisa jadi terkena filter keamanan)")
        return kandidat[0]["content"]