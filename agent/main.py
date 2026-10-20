import dataclasses
import logging
import sys
from http.server import ThreadingHTTPServer

from alat.daftar import KotakAlat
from config import muat
from handler import buat_penangan
from llm.client import KlienCadangan, buat_klien
from prompt import INSTRUKSI_SISTEM, INSTRUKSI_TAMU
from service import Agen


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = muat()

    try:
        klien, nama_model = buat_klien(cfg)
        klien_tamu, nama_tamu = buat_klien(cfg, cfg.llm_model_tamu) if cfg.llm_model_tamu else (klien, nama_model)
        if cfg.llm_model_cadangan:
            cadangan, _ = buat_klien(cfg, cfg.llm_model_cadangan)
            klien, klien_tamu = KlienCadangan(klien, cadangan), KlienCadangan(klien_tamu, cadangan)
    except ValueError as galat:
        sys.exit(str(galat))
    if not cfg.api_key:
        sys.exit("AGENT_API_KEY wajib diisi di .env")
    if not cfg.tavily_api_key:
        logging.warning("TAVILY_API_KEY kosong: agent hanya bisa membaca URL, tidak bisa mencari")

    agen = Agen(klien, KotakAlat(cfg), cfg.maks_langkah, cfg.verifikasi_jawaban)
    # tamu memakai profil hemat: model sendiri (jika diisi), langkah lebih sedikit, dan pencarian Tavily basic
    cfg_tamu = dataclasses.replace(cfg, tavily_kedalaman="basic", maks_baca_url=cfg.tamu_maks_baca_url)
    agen_tamu = Agen(klien_tamu, KotakAlat(cfg_tamu), cfg.tamu_maks_langkah, cfg.verifikasi_jawaban, INSTRUKSI_SISTEM + INSTRUKSI_TAMU)

    server = ThreadingHTTPServer((cfg.host, cfg.port), buat_penangan(agen, agen_tamu, cfg.api_key))
    logging.info("layanan agent jalan di http://%s:%d (%s, model %s, model tamu %s, cadangan %s)", cfg.host, cfg.port,
                 cfg.llm_provider, nama_model, nama_tamu, cfg.llm_model_cadangan or "-")
    server.serve_forever()


if __name__ == "__main__":
    main()