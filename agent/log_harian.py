"""Log harian di lokal: semua keluaran terminal agent ditambah isi lengkap setiap permintaan dan balasan LLM, satu berkas per tanggal
(log/2026-11-20.log di folder proyek) yang dipakai bersama backend dan gerbang-local; setiap baris diawali nama bagiannya.
Mati di Render (Render selalu mengisi variabel RENDER); folder log/ ada di .gitignore."""
import hashlib
import itertools
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from llm import pemakaian

FOLDER_LOG = Path(__file__).resolve().parent.parent / "log"
LABEL = f"{'agent':<13} | "
# baris yang datang terus-menerus dari backend (cek status tiap beberapa detik) tidak ditulis, agar log mudah dibaca
BARIS_SEPI = ('"GET /kesehatan ', '"POST /embed-info ')
GARIS_TEBAL = "=" * 100
GARIS = "-" * 100
INDEN = "    "

_aktif = False
_gembok = threading.Lock()
_berkas = {"tanggal": None, "isi": None, "sisa": ""}
# instruksi sistem yang sama (ribuan huruf) cukup ditulis lengkap sekali per hari
_instruksi_tertulis = set()
_nomor = itertools.count(1)


def pasang():
    """Dipanggil paling awal di main, sebelum logging diatur; mengembalikan keterangan untuk tabel awal."""
    global _aktif
    if os.environ.get("RENDER"):
        return "mati di Render"
    try:
        FOLDER_LOG.mkdir(parents=True, exist_ok=True)
    except OSError as galat:
        return f"mati, folder log tidak bisa dibuat: {galat}"
    _aktif = True
    sys.stdout, sys.stderr = Cabang(sys.stdout), Cabang(sys.stderr)
    tulis(f"\n{GARIS_TEBAL}\nAGENT MENYALA {datetime.now():%Y-%m-%d %H:%M:%S}\n{GARIS_TEBAL}\n")
    return f"aktif, {FOLDER_LOG}{os.sep}<tanggal>.log"


def tulis(teks):
    if not _aktif:
        return
    with _gembok:
        # hanya baris utuh yang ditulis, sekaligus dalam satu kali tulis, agar tidak tercampur dengan tulisan backend di berkas yang sama
        teks = _berkas["sisa"] + teks
        akhir = teks.rfind("\n") + 1
        _berkas["sisa"] = teks[akhir:]
        if not akhir:
            return
        tanggal = datetime.now().strftime("%Y-%m-%d")
        if _berkas["tanggal"] != tanggal:
            if _berkas["isi"]:
                _berkas["isi"].close()
            _berkas["isi"] = open(FOLDER_LOG / f"{tanggal}.log", "a", encoding="utf-8", newline="")
            _berkas["tanggal"] = tanggal
            _instruksi_tertulis.clear()
        _berkas["isi"].write("".join(f"{LABEL}{baris}\n" for baris in teks[:akhir - 1].split("\n")))
        _berkas["isi"].flush()


class Cabang:
    """Meneruskan tulisan ke terminal seperti biasa sekaligus ke berkas log hari ini."""

    def __init__(self, asli):
        self.asli = asli

    def write(self, teks):
        hasil = self.asli.write(teks) if self.asli else len(teks)
        if not any(baris in teks for baris in BARIS_SEPI):
            tulis(teks)
        return hasil

    def flush(self):
        if self.asli:
            self.asli.flush()

    def __getattr__(self, nama):
        return getattr(self.asli, nama)


def mulai_permintaan(jenis, pertanyaan):
    """Judul satu permintaan (jawaban atau ringkasan); panggilan LLM sesudahnya diberi nomor yang sama."""
    if not _aktif:
        return
    nomor = next(_nomor)
    catatan = pemakaian.bawa()
    if catatan is not None:
        catatan["_nomor"], catatan["_mulai"], catatan["_pesan_tertulis"] = nomor, time.monotonic(), set()
    tulis(f"\n{GARIS_TEBAL}\n#{nomor} {jenis.upper()} | {datetime.now():%Y-%m-%d %H:%M:%S}\n{rapikan(pertanyaan)}\n{GARIS_TEBAL}\n")


def selesai_permintaan(alat=None, jawaban="", galat=None):
    if not _aktif:
        return
    catatan = pemakaian.bawa() or {}
    if "_nomor" not in catatan:
        return
    lama = time.monotonic() - catatan["_mulai"]
    keadaan = f"GAGAL: {galat}" if galat else "selesai"
    ringkas = (f"#{catatan['_nomor']} {keadaan} | {lama:.1f} detik | {catatan['panggilan_llm']} panggilan LLM | "
               f"token masuk {angka(catatan['token_masuk'])} keluar {angka(catatan['token_keluar'])}")
    isi = [GARIS, ringkas, f"alat: {', '.join(alat or []) or '-'}"]
    if jawaban:
        isi += ["[jawaban akhir]", inden(jawaban)]
    tulis("\n" + "\n".join(isi + [GARIS_TEBAL]) + "\n")


class KlienTercatat:
    """Membungkus klien LLM: setiap panggilan ditulis ke log harian (instruksi, alat, pesan, balasan, token, lama, galat)."""

    def __init__(self, klien, model):
        self.klien = klien
        self.nama_model = model

    def kirim(self, instruksi_sistem, isi_percakapan, deklarasi_alat=None, wajib_alat=False, saat_teks=None):
        if not _aktif:
            return self.klien.kirim(instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, saat_teks)
        pemakaian.ambil_terakhir()
        mulai = time.monotonic()
        try:
            balasan = self.klien.kirim(instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, saat_teks)
        except Exception as galat:
            catat_llm(self.nama_model, instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, saat_teks, None, galat,
                      time.monotonic() - mulai)
            raise
        catat_llm(self.nama_model, instruksi_sistem, isi_percakapan, deklarasi_alat, wajib_alat, saat_teks, balasan, None,
                  time.monotonic() - mulai)
        return balasan

    def __getattr__(self, nama):
        return getattr(self.klien, nama)


def catat_llm(model, instruksi, pesan, alat, wajib, stream, balasan, galat, detik):
    catatan = pemakaian.bawa() or {}
    nomor = f"#{catatan['_nomor']}" if "_nomor" in catatan else "#-"
    tertulis = catatan.setdefault("_pesan_tertulis", set()) if "_nomor" in catatan else set()
    cara = ["stream" if stream else "biasa"] + (["wajib alat"] if wajib else [])
    baris = ["", GARIS, f"{nomor} LLM {model} | {datetime.now():%H:%M:%S} | {', '.join(cara)}", GARIS]

    kunci = hashlib.sha1(instruksi.encode("utf-8")).hexdigest()[:8]
    with _gembok:
        baru = kunci not in _instruksi_tertulis
        _instruksi_tertulis.add(kunci)
    if baru:
        baris += [f"[instruksi sistem {kunci}, {angka(len(instruksi))} huruf]", inden(instruksi)]
    else:
        pertama = instruksi.strip().split("\n", 1)[0][:90]
        baris.append(f"[instruksi sistem {kunci}, sama seperti yang sudah ditulis hari ini] {pertama}")
    if alat:
        baris.append(f"[alat] {', '.join(d.get('name', '?') for d in alat)}")

    lewat, awal = 0, len(baris)
    for i, isi in enumerate(pesan or [], 1):
        sidik = hashlib.sha1(json.dumps(isi, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
        if sidik in tertulis:
            lewat += 1
            continue
        tertulis.add(sidik)
        baris += [f"[pesan {i} | {isi.get('role', '?')}]", inden(teks_blok(isi.get("content")))]
    if lewat:
        baris.insert(awal, f"[{lewat} pesan sama dengan panggilan sebelumnya di permintaan ini, tidak ditulis ulang]")

    masuk, keluar = pemakaian.ambil_terakhir()
    hasil = f"GAGAL: {galat}" if galat else "balasan"
    baris += [f"--- {hasil} | {detik:.1f} detik | token masuk {angka(masuk)} keluar {angka(keluar)} ---"]
    if balasan:
        baris.append(inden(teks_blok(balasan.get("content"))))
    tulis("\n".join(baris) + "\n")
    logging.info("LLM %s %s: %.1f detik, token masuk %d keluar %d, %s", nomor, model, detik, masuk, keluar, ringkas_balasan(balasan, galat))


def ringkas_balasan(balasan, galat):
    """Satu baris untuk terminal: alat yang dipanggil model, atau panjang teks jawabannya."""
    if galat:
        return f"gagal: {galat}"
    konten = (balasan or {}).get("content") or []
    alat = [b["toolUse"].get("name", "?") for b in konten if "toolUse" in b]
    if alat:
        return "memanggil " + ", ".join(alat)
    return f"teks {sum(len(b.get('text', '')) for b in konten)} huruf"


def teks_blok(konten):
    """Isi pesan format Bedrock (text, image, toolUse, toolResult) sebagai teks yang mudah dibaca."""
    if isinstance(konten, str):
        return konten
    bagian = []
    for blok in konten or []:
        if "text" in blok:
            bagian.append(blok["text"])
        elif "image" in blok:
            gambar = blok["image"]
            ukuran = len((gambar.get("source") or {}).get("bytes") or "") * 3 // 4
            bagian.append(f"[gambar {gambar.get('format', '?')}, {ukuran // 1024} KB]")
        elif "toolUse" in blok:
            pakai = blok["toolUse"]
            bagian.append(f"-> memanggil {pakai.get('name')} ({pakai.get('toolUseId', '')}): "
                          f"{json.dumps(pakai.get('input'), ensure_ascii=False)}")
        elif "toolResult" in blok:
            hasil = blok["toolResult"]
            isi = "\n".join(rapikan_json(b.get("text", "")) if "text" in b else json.dumps(b.get("json", b), ensure_ascii=False, indent=2)
                            for b in hasil.get("content") or [])
            bagian.append(f"<- hasil alat ({hasil.get('toolUseId', '')}):\n{isi}")
        else:
            bagian.append(json.dumps(blok, ensure_ascii=False, default=str)[:2000])
    return "\n".join(bagian)


def rapikan_json(teks):
    try:
        return json.dumps(json.loads(teks), ensure_ascii=False, indent=2)
    except ValueError:
        return teks


def angka(n):
    return f"{n:,}".replace(",", ".")


def rapikan(teks):
    return " ".join(str(teks or "").split())[:1000]


def inden(teks):
    return "\n".join(INDEN + b for b in str(teks or "").split("\n"))
