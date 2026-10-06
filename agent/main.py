import logging
import sys
from http.server import ThreadingHTTPServer

from alat.daftar import KotakAlat
from config import muat
from handler import buat_penangan
from llm.client import buat_klien
from service import Agen


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = muat()

    try:
        klien, nama_model = buat_klien(cfg)
    except ValueError as galat:
        sys.exit(str(galat))
    if not cfg.api_key:
        sys.exit("AGENT_API_KEY wajib diisi di .env")
    if not cfg.tavily_api_key:
        logging.warning("TAVILY_API_KEY kosong: agent hanya bisa membaca URL, tidak bisa mencari")

    agen = Agen(klien, KotakAlat(cfg), cfg.maks_langkah)

    server = ThreadingHTTPServer((cfg.host, cfg.port), buat_penangan(agen, cfg.api_key))
    logging.info("layanan agent jalan di http://%s:%d (%s, model %s)", cfg.host, cfg.port, cfg.llm_provider, nama_model)
    server.serve_forever()


if __name__ == "__main__":
    main()