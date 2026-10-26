import dataclasses
import logging
import sys
from http.server import ThreadingHTTPServer
from alat.cache_cari import CacheCari
from alat.daftar import KotakAlat
from alat.tambahan import AlatTambahan
from config import muat
from handler import buat_penangan
from llm.client import KlienCadangan, buat_klien
from llm.embedding import buat_pembuat_embedding
from prompt import INSTRUKSI_CEPAT, INSTRUKSI_MENDALAM, INSTRUKSI_SISTEM, INSTRUKSI_TAMU
from service import Agen


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = muat()

    try:
        klien, nama_model = buat_klien(cfg)
        klien_cepat, nama_cepat = buat_klien(cfg, cfg.llm_model_cepat) if cfg.llm_model_cepat else (klien, nama_model)
        klien_tamu, nama_tamu = buat_klien(cfg, cfg.llm_model_tamu) if cfg.llm_model_tamu else (klien_cepat, nama_cepat)
        if cfg.llm_model_cadangan:
            cadangan, _ = buat_klien(cfg, cfg.llm_model_cadangan)
            klien, klien_cepat, klien_tamu = (KlienCadangan(k, cadangan) for k in (klien, klien_cepat, klien_tamu))
    except ValueError as galat:
        sys.exit(str(galat))
    if not cfg.api_key:
        sys.exit("AGENT_API_KEY wajib diisi di .env")
    if not cfg.tavily_api_key:
        logging.warning("TAVILY_API_KEY kosong: agent hanya bisa membaca URL, tidak bisa mencari")

    # mendalam = model utama dengan langkah penuh; cepat = tanpa wajib cari, langkah lebih sedikit, Tavily basic;
    # tamu = seperti cepat ditambah jawaban lebih singkat
    cfg_cepat = dataclasses.replace(cfg, wajib_cari=False, tavily_kedalaman="basic", maks_baca_url=cfg.cepat_maks_baca_url)
    cfg_tamu = dataclasses.replace(cfg, tavily_kedalaman="basic", maks_baca_url=cfg.tamu_maks_baca_url)
    # satu cache dipakai bersama semua profil agar kueri yang sama tidak memakai kredit Tavily dua kali
    cache = CacheCari(cfg.cache_cari_detik, cfg.cache_cari_maks)
    tambahan = AlatTambahan(cfg.alat)
    logging.info("alat tambahan aktif: %s", ", ".join(tambahan.alat) or "-")
    daftar_agen = {
        "mendalam": Agen(klien, KotakAlat(cfg, cache, tambahan), cfg.maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_MENDALAM),
        "cepat": Agen(klien_cepat, KotakAlat(cfg_cepat, cache, tambahan), cfg.cepat_maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_CEPAT),
        "tamu": Agen(klien_tamu, KotakAlat(cfg_tamu, cache, tambahan), cfg.tamu_maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_TAMU),
    }

    pembuat_embedding = buat_pembuat_embedding(cfg)

    server = ThreadingHTTPServer((cfg.host, cfg.port), buat_penangan(daftar_agen, cfg.api_key, pembuat_embedding, cfg.alat.berkas_maks_huruf))
    logging.info("layanan agent jalan di http://%s:%d (%s, model mendalam %s, cepat %s, tamu %s, cadangan %s)", cfg.host, cfg.port,
                 cfg.llm_provider, nama_model, nama_cepat, nama_tamu, cfg.llm_model_cadangan or "-")
    server.serve_forever()


if __name__ == "__main__":
    main()