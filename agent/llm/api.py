import json
import logging
import urllib.error
import urllib.request

from llm import denyut, pemakaian
from llm.client import GalatLLM, buka, kirim_json

# perkiraan kasar agar aman: satu token rata-rata 3 huruf (teks Indonesia dan JSON hasil alat)
HURUF_PER_TOKEN = 3
MIN_HURUF_ALAT = 1500
SISA_RIWAYAT = 4
TANDA_POTONG = " ...(dipotong agar muat di konteks model)"

class KlienAPI:
    def __init__(self, alamat, api_key, model, batas_waktu=60, penalaran="", batas_konteks=0):
        """batas_konteks = token prompt terbanyak; 0 = tidak dipangkas (penyedia API memberi galat sendiri jika penuh)."""
        self.alamat = alamat.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batas_waktu = batas_waktu
        self.penalaran = penalaran
        self.batas_konteks = batas_konteks


    def sehat(self, batas_waktu=5):
        """Cek GET /models untuk status AI di frontend: True = terhubung; False = pasti mati (koneksi ditolak,
        alamat tidak ditemukan, atau gerbang/tunnel membalas galat); None = hanya lambat membalas, misalnya laptop sedang sibuk."""
        hasil, alasan = self.periksa(batas_waktu)
        if not hasil:
            logging.warning("cek LLM %s", alasan)
        return hasil

    def periksa(self, batas_waktu=5):
        """Sama seperti sehat, tetapi tanpa mencatat log; hasilnya (status, alasan) untuk tabel awal agent."""
        header = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{self.alamat}/models", headers=header), timeout=batas_waktu) as respon:
                return respon.status == 200, f"kode {respon.status}"
        except TimeoutError:
            return None, f"lambat: lebih dari {batas_waktu} detik"
        except urllib.error.HTTPError as galat:
            return False, f"gagal: kode {galat.code}"
        except urllib.error.URLError as galat:
            if isinstance(galat.reason, TimeoutError):
                return None, f"lambat: lebih dari {batas_waktu} detik"
            return False, f"gagal: {galat.reason}"
        except (OSError, ValueError) as galat:
            return False, f"gagal: {galat}"

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None, wajib_alat=False, saat_teks=None):
        """Mengirim percakapan ke layanan berformat OpenAI (chat/completions) dan mengembalikan pesan balasan model.
        Jika saat_teks diisi, balasan diminta sebagai stream dan saat_teks(potongan) dipanggil setiap ada teks baru."""
        pesan = [{"role": "system", "content": instruksi_sistem}]
        for giliran in isi_percakapan:
            pesan.extend(ke_format_api(giliran))

        badan = {"model": self.model, "messages": pesan}
        if self.penalaran:
            badan["reasoning_effort"] = self.penalaran
        if deklarasi_alat:
            badan["tools"] = [{"type": "function", "function": d} for d in deklarasi_alat]
            if wajib_alat:
                badan["tool_choice"] = "required"
        if self.batas_konteks:
            muat_konteks(pesan, badan.get("tools"), self.batas_konteks)

        header = {"Content-Type": "application/json"}
        if self.api_key:
            header["Authorization"] = f"Bearer {self.api_key}"
        alamat = f"{self.alamat}/chat/completions"
        if saat_teks:
            badan["stream"] = True
            if self.batas_konteks:
                # Ollama baru mengirim jumlah token di akhir stream jika diminta; dipakai halaman kinerja
                badan["stream_options"] = {"include_usage": True}
            with buka(alamat, json.dumps(badan).encode("utf-8"), header, self.batas_waktu, "Layanan LLM") as respon:
                balasan, alasan = rakit_pesan_stream(respon, saat_teks)
            pakai = None
        else:
            data = kirim_json(alamat, json.dumps(badan).encode("utf-8"), header, self.batas_waktu, "Layanan LLM")
            pilihan = data.get("choices") or []
            if not pilihan or not pilihan[0].get("message"):
                raise GalatLLM("Layanan LLM tidak memberi jawaban")
            balasan, alasan, pakai = pilihan[0]["message"], pilihan[0].get("finish_reason"), data.get("usage")
            catat_token(pakai)
        try:
            return dari_format_api(balasan)
        except GalatLLM as galat:
            # info tambahan untuk melacak balasan kosong, misalnya prompt terpotong karena konteks model penuh
            raise GalatLLM(f"{galat} (finish_reason={alasan}, usage={pakai})", galat.kode)

def panjang(pesan):
    isi = pesan.get("content")
    if isinstance(isi, list):
        isi = " ".join(b.get("text", "") for b in isi if b.get("type") == "text")
    return len(isi or "") + (len(json.dumps(pesan["tool_calls"], ensure_ascii=False)) if pesan.get("tool_calls") else 0)


def jatah_rata(daftar_panjang, total):
    """Batas huruf yang sama untuk semua hasil alat agar jumlahnya muat di total; hasil yang pendek tidak dipotong."""
    sisa = len(daftar_panjang)
    for n in sorted(daftar_panjang):
        rata = total // sisa
        if n > rata:
            return rata
        total -= n
        sisa -= 1
    return max(daftar_panjang)


def muat_konteks(pesan, alat, batas_token):
    """Ollama membuang awal percakapan tanpa pemberitahuan jika prompt melebihi konteksnya, sehingga riwayat hilang.
    Agar itu tidak terjadi: riwayat paling lama dibuang berpasangan dulu, lalu hasil alat dipendekkan rata,
    terakhir pesan terpanjang diambil awal dan akhirnya saja."""
    lebih = sum(panjang(p) for p in pesan) + len(json.dumps(alat or [], ensure_ascii=False)) - batas_token * HURUF_PER_TOKEN
    if lebih <= 0:
        return
    awal_lebih, dibuang = lebih, 0

    # riwayat = pesan sebelum pertanyaan sekarang; empat pesan terakhirnya tetap dikirim agar rujukan seperti "game itu" terbaca
    mulai_alat = next((i for i, p in enumerate(pesan) if p.get("role") == "tool" or p.get("tool_calls")), len(pesan))
    sekarang = max((i for i in range(1, mulai_alat) if pesan[i].get("role") == "user"), default=1)
    while lebih > 0 and sekarang - 1 > SISA_RIWAYAT:
        lebih -= panjang(pesan[1]) + panjang(pesan[2])
        del pesan[1:3]
        sekarang -= 2
        dibuang += 2

    hasil_alat = [p for p in pesan if p.get("role") == "tool" and isinstance(p.get("content"), str)]
    if lebih > 0 and hasil_alat:
        total = sum(len(p["content"]) for p in hasil_alat)
        jatah = max(jatah_rata([len(p["content"]) for p in hasil_alat], total - lebih - len(TANDA_POTONG) * len(hasil_alat)), MIN_HURUF_ALAT)
        for p in hasil_alat:
            if len(p["content"]) > jatah:
                lebih -= len(p["content"]) - jatah - len(TANDA_POTONG)
                p["content"] = p["content"][:jatah] + TANDA_POTONG

    while lebih > 0:
        terpanjang = max((p for p in pesan[1:] if isinstance(p.get("content"), str)), key=panjang, default=None)
        isi = terpanjang["content"] if terpanjang else ""
        sisa = max(len(isi) - lebih - len(TANDA_POTONG), MIN_HURUF_ALAT * 2)
        if len(isi) <= sisa + len(TANDA_POTONG):
            break
        terpanjang["content"] = isi[:sisa - MIN_HURUF_ALAT] + TANDA_POTONG + isi[-MIN_HURUF_ALAT:]
        lebih -= len(isi) - len(terpanjang["content"])
    logging.warning("prompt melebihi konteks model sekitar %d token dan dipangkas, %d pesan riwayat lama dibuang%s",
                    awal_lebih // HURUF_PER_TOKEN, dibuang, "" if lebih <= 0 else ", masih terlalu panjang")


def catat_token(usage):
    """Format OpenAI melaporkan token sebagai prompt_tokens dan completion_tokens; tanpa usage tetap dihitung satu panggilan."""
    usage = usage if isinstance(usage, dict) else {}
    pemakaian.catat(usage.get("prompt_tokens"), usage.get("completion_tokens"))

def rakit_pesan_stream(respon, saat_teks):
    """Menyusun kembali pesan utuh dari baris "data: {...}" stream format OpenAI, sambil meneruskan teksnya."""
    teks, panggilan, alasan, pakai = "", {}, None, None
    for baris in respon:
        denyut.detak()
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
        # hanya sebagian layanan yang mengirim jumlah token di akhir stream
        pakai = data.get("usage") or pakai

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
    catat_token(pakai)

    pesan = {"role": "assistant", "content": teks or None}
    if panggilan:
        pesan["tool_calls"] = [panggilan[nomor] for nomor in sorted(panggilan)]
    return pesan, alasan

def ke_format_api(giliran):
    """Mengubah satu giliran berbentuk internal (content berisi text/image/toolUse/toolResult) ke pesan format OpenAI."""
    isi = giliran.get("content", [])
    hasil_alat = [b["toolResult"] for b in isi if "toolResult" in b]
    teks = "".join(b.get("text", "") for b in isi)
    if hasil_alat:
        pesan = [{"role": "tool", "tool_call_id": h["toolUseId"], "content": h["content"][0]["text"]}
                 for h in hasil_alat]
        if teks:
            pesan.append({"role": "user", "content": teks})
        return pesan

    gambar = [b["image"] for b in isi if "image" in b]
    pesan = {"role": giliran.get("role", "user"), "content": teks or None}
    if gambar:
        # format OpenAI: gambar dikirim sebagai data URL di samping teks
        pesan["content"] = [{"type": "image_url", "image_url": {"url": f"data:image/{g['format']};base64,{g['source']['bytes']}"}}
                            for g in gambar] + ([{"type": "text", "text": teks}] if teks else [])
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