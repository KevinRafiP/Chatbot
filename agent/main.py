import logging
import sys
from http.server import ThreadingHTTPServer

from alat import KotakAlat
from config import muat
from handler import buat_penangan
from llm.client import Klien
from service import Agen


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = muat()

    if not cfg.gemini_api_key:
        sys.exit("GEMINI_API_KEY wajib diisi di .env")
    if not cfg.api_key:
        sys.exit("AGENT_API_KEY wajib diisi di .env")
    if not cfg.tavily_api_key:
        logging.warning("TAVILY_API_KEY kosong: agent hanya bisa membaca URL, tidak bisa mencari")

    klien = Klien(cfg.gemini_api_key, cfg.gemini_model)
    agen = Agen(klien, KotakAlat(cfg), cfg.maks_langkah)

    server = ThreadingHTTPServer((cfg.host, cfg.port), buat_penangan(agen, cfg.api_key))
    logging.info("layanan agent jalan di http://%s:%d (model %s)", cfg.host, cfg.port, cfg.gemini_model)
    server.serve_forever()


if __name__ == "__main__":
    main()