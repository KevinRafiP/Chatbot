import re
from urllib.parse import urlparse

from alat.tingkat import cocok_domain

# topik dikenali dari kata di kueri dan pertanyaan; domainnya bisa diganti lewat env SUMBER_UTAMA_<TOPIK>
TOPIK = {
    "game": (r"\b(game|games|gim|gacha|operator|skill|skills|talent|boss|quest|dlc|build|tier list|banner|steam|playstation|ps4|ps5|"
             r"nintendo|switch|xbox|rpg|jrpg|mmorpg|moba|fps|arknights|genshin|honkai|zenless|wuthering|blue archive|fate grand order|"
             r"pokemon|zelda|final fantasy|persona|elden ring|minecraft|valorant|dota|mobile legends)\b",
             ("wiki.gg", "fandom.com", "gamepress.gg", "game8.co", "ign.com", "prydwen.gg")),
    "anime": (r"\b(anime|manga|manhwa|manhua|donghua|light novel|episode|studio animasi|seiyuu|pengisi suara|voice actor|mangaka|"
              r"isekai|shonen|shounen|shoujo|seinen)\b",
              ("myanimelist.net", "anilist.co", "animenewsnetwork.com", "fandom.com", "wikipedia.org")),
    "pemrograman": (r"\b(python|javascript|typescript|golang|java|kotlin|rust|php|react|vue|node|nodejs|django|laravel|sql|postgres|"
                    r"docker|kubernetes|api|library|framework|error|exception|bug|coding|programming|pemrograman|fungsi|syntax|sintaks)\b",
                    ("developer.mozilla.org", "docs.python.org", "go.dev", "pkg.go.dev", "react.dev", "stackoverflow.com",
                     "learn.microsoft.com", "github.com")),
    "kesehatan": (r"\b(penyakit|gejala|obat|dosis|vaksin|virus|bakteri|infeksi|kesehatan|dokter|diet|gizi|nutrisi|kanker|diabetes|"
                  r"hipertensi|kolesterol|demam|batuk|alergi|kehamilan|hamil)\b",
                  ("who.int", "kemkes.go.id", "alodokter.com", "halodoc.com", "mayoclinic.org", "cdc.gov")),
    "teknologi": (r"\b(windows|macos|mac os|ubuntu|linux|android|ios|iphone|ipad|whatsapp|telegram|microsoft|office 365|microsoft 365|"
                  r"ms word|excel|powerpoint|outlook|onedrive|chrome|gmail|google drive|wifi|wi-fi|bluetooth|printer|bios|driver|"
                  r"zip|rar|7-zip|winrar|file explorer|task manager|pengaturan|settings)\b",
                  ("support.microsoft.com", "learn.microsoft.com", "support.apple.com", "support.google.com", "faq.whatsapp.com",
                   "help.ubuntu.com")),
    "berita": (r"\b(berita|terbaru|terkini|hari ini|kemarin|pekan ini|minggu ini|pemilu|pilkada|presiden|menteri|dpr|kebijakan|"
               r"demo|bencana|banjir)\b",
               ("antaranews.com", "kompas.com", "tempo.co", "detik.com", "cnnindonesia.com", "bbc.com", "reuters.com")),
}
POLA_TOPIK = {nama: re.compile(pola, re.IGNORECASE) for nama, (pola, _) in TOPIK.items()}


def domain_bawaan():
    return {nama: list(domain) for nama, (_, domain) in TOPIK.items()}


class SumberUtama:
    """Domain yang diutamakan per topik: hasil dari domain ini diletakkan paling atas dan dibuka lebih dulu."""

    def __init__(self, daftar):
        # daftar = {topik: [domain, ...]}; topik dengan daftar kosong berarti mati
        self.daftar = {nama: domain for nama, domain in daftar.items() if domain and nama in POLA_TOPIK}

    def domain(self, teks):
        """Domain utama untuk semua topik yang cocok dengan teks, tanpa dobel, urut sesuai topik."""
        hasil = []
        for nama, domain in self.daftar.items():
            if POLA_TOPIK[nama].search(teks or ""):
                hasil += [d for d in domain if d not in hasil]
        return hasil

    @staticmethod
    def dari(url, domain):
        return bool(domain) and cocok_domain((urlparse(url).hostname or "").lower(), domain)