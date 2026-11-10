import dataclasses
import functools
import logging
import sys
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
from alat.cache_cari import CacheCari
from alat.cari import PencariBerantai
from alat.daftar import KotakAlat
from alat.tambahan import AlatTambahan
from config import muat
from handler import buat_penangan
from llm.client import CekLLM, KlienCadangan, buat_klien
from llm.cari_gambar import buat_pencari_gambar
from llm.embedding import buat_pembuat_embedding
from llm.gambar import PembacaGambar
from log_awal import aktif_mati, cetak_tabel
from prompt import INSTRUKSI_BACA_BANYAK, INSTRUKSI_CEPAT, INSTRUKSI_MENDALAM, INSTRUKSI_SISTEM, INSTRUKSI_TAMU
from service import Agen
from tulis_ulang import tulis_ulang

NAMA_PENYEDIA_LLM = {"local": "Lokal (Ollama)", "aws": "AWS Bedrock", "api": "API berformat OpenAI"}


def alamat_llm(cfg):
    """Alamat layanan model tanpa kunci; untuk API hanya nama hostnya."""
    if cfg.llm_provider == "local":
        return cfg.local_url
    if cfg.llm_provider == "api":
        return urlparse(cfg.api_url).netloc or "-"
    return f"region {cfg.aws_region}"


def koneksi_llm(klien):
    """Mencoba menghubungi model sekali saat menyala; AWS tidak punya cek ringan, jadi baru teruji saat menjawab."""
    periksa = getattr(klien, "periksa", None)
    if periksa is None:
        return "tidak dicek, diuji saat pertanyaan pertama"
    hasil, alasan = periksa()
    if hasil:
        return "tersambung"
    return f"belum tersambung ({alasan})"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = muat()

    try:
        klien, nama_model = buat_klien(cfg)
        # dicek sebelum dibungkus model cadangan, agar status di frontend menunjukkan model utama
        cek_llm = CekLLM(klien)
        koneksi = koneksi_llm(klien)
        klien_cepat, nama_cepat = buat_klien(cfg, cfg.llm_model_cepat) if cfg.llm_model_cepat else (klien, nama_model)
        klien_tamu, nama_tamu = buat_klien(cfg, cfg.llm_model_tamu) if cfg.llm_model_tamu else (klien_cepat, nama_cepat)
        klien_gambar = buat_klien(cfg, cfg.model_gambar)[0] if cfg.model_gambar else klien
        klien_periksa = buat_klien(cfg, cfg.llm_model_periksa)[0] if cfg.llm_model_periksa else klien_cepat
        # penulis ulang pertanyaan lanjutan memakai model utama kecuali LLM_MODEL_TULIS_ULANG diisi, dengan batas waktu sendiri
        klien_tulis = buat_klien(cfg, cfg.llm_model_tulis)[0]
        klien_tulis.batas_waktu = cfg.tulis_batas_detik
        if cfg.llm_model_cadangan:
            cadangan, _ = buat_klien(cfg, cfg.llm_model_cadangan)
            klien, klien_cepat, klien_tamu = (KlienCadangan(k, cadangan) for k in (klien, klien_cepat, klien_tamu))
    except ValueError as galat:
        sys.exit(str(galat))
    if not cfg.api_key:
        sys.exit("AGENT_API_KEY wajib diisi di .env")
    # satu pencari dipakai bersama semua profil agar penyedia yang habis tidak dicoba ulang oleh profil lain
    pencari = PencariBerantai(cfg.penyedia_cari, cfg.cari_jeda_detik)

    # mendalam = model utama dengan langkah penuh; cepat = tanpa wajib cari, langkah lebih sedikit, Tavily basic;
    # tamu = seperti cepat ditambah jawaban lebih singkat
    cfg_cepat = dataclasses.replace(cfg, wajib_cari=cfg.wajib_cari and cfg.cepat_wajib_cari, cari_kedalaman="basic", maks_baca_url=cfg.cepat_maks_baca_url)
    cfg_tamu = dataclasses.replace(cfg, cari_kedalaman="basic", maks_baca_url=cfg.tamu_maks_baca_url)
    # satu cache dipakai bersama semua profil agar kueri yang sama tidak memakai kredit Tavily dua kali
    cache = CacheCari(cfg.cache_cari_detik, cfg.cache_cari_maks)
    tambahan = AlatTambahan(cfg.alat)
    # pemeriksa logika hanya untuk mode mendalam, karena menambah satu panggilan model
    pemeriksa = (klien_periksa, cfg.periksa_huruf_sumber) if cfg.periksa_logika else None
    penulis = functools.partial(tulis_ulang, klien_tulis)
    daftar_agen = {
        "mendalam": Agen(klien, KotakAlat(cfg, cache, tambahan, pencari), cfg.maks_langkah, cfg.verifikasi_jawaban,
                         INSTRUKSI_SISTEM + INSTRUKSI_MENDALAM + (INSTRUKSI_BACA_BANYAK if cfg.baca_banyak else ""),
                         pemeriksa, penulis),
        "cepat": Agen(klien_cepat, KotakAlat(cfg_cepat, cache, tambahan, pencari), cfg.cepat_maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_CEPAT, penulis=penulis),
        "tamu": Agen(klien_tamu, KotakAlat(cfg_tamu, cache, tambahan, pencari), cfg.tamu_maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_TAMU, penulis=penulis),
    }

    pembuat_embedding, ket_embedding = buat_pembuat_embedding(cfg)
    # foto soal dibaca model vision menjadi teks; BACA_GAMBAR=tidak mematikannya
    pencari_gambar, ket_cari_gambar = buat_pencari_gambar(cfg)
    pembaca_gambar = PembacaGambar(klien_gambar, pencari_gambar) if cfg.baca_gambar else None

    server = ThreadingHTTPServer((cfg.host, cfg.port), buat_penangan(daftar_agen, cfg.api_key, pembuat_embedding, cfg.alat.berkas_maks_huruf,
                                                                     pembaca_gambar, cek_llm))
    baris = [
        ("LLM provider", NAMA_PENYEDIA_LLM.get(cfg.llm_provider, cfg.llm_provider)),
        ("Alamat LLM", alamat_llm(cfg)),
        ("Koneksi LLM", koneksi),
        ("Model mendalam", nama_model),
        ("Model cepat", nama_cepat),
        ("Model tamu", nama_tamu),
        ("Model cadangan", cfg.llm_model_cadangan or "-"),
        ("Penyedia cari", ", ".join(pencari.nama()) if pencari.ada() else "mati, CARI_PENYEDIA atau kuncinya kosong (hanya baca URL)"),
        ("Alat tambahan", ", ".join(tambahan.alat) or "-"),
    ]
    if tambahan.tidak_aktif:
        baris.append(("Alat belum diatur", ", ".join(tambahan.tidak_aktif)))
    baris += [
        ("Pemeriksa logika", aktif_mati(pemeriksa is not None, "mode mendalam" if pemeriksa else "")),
        ("Verifikasi jawaban", aktif_mati(cfg.verifikasi_jawaban)),
        ("Pencarian makna", ket_embedding),
        ("Baca gambar", aktif_mati(pembaca_gambar is not None, f"model {cfg.model_gambar or nama_model}" if pembaca_gambar else "")),
        ("Cari asal gambar", ket_cari_gambar if pembaca_gambar else "mati"),
        ("Alamat agent", f"http://{cfg.host}:{cfg.port}"),
    ]
    cetak_tabel("Vokapas agent", baris)
    server.serve_forever()


if __name__ == "__main__":
    main()