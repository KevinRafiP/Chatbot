from urllib.parse import urlparse

# kuat: wiki, ensiklopedia, berita, dan situs lembaga
DOMAIN_KUAT = (
    "wikipedia.org", "fandom.com", "wiki.gg", "britannica.com",
    "kompas.com", "detik.com", "tempo.co", "antaranews.com", "cnnindonesia.com", "cnbcindonesia.com",
    "bbc.com", "bbc.co.uk", "reuters.com", "apnews.com", "theguardian.com", "nytimes.com",
)
AKHIRAN_KUAT = (".go.id", ".ac.id", ".sch.id", ".gov", ".edu", ".wiki")

# lemah: video, komentar, forum, dan media sosial
DOMAIN_LEMAH = (
    "youtube.com", "youtu.be", "reddit.com", "x.com", "twitter.com", "facebook.com", "instagram.com",
    "tiktok.com", "threads.net", "quora.com", "kaskus.co.id", "steamcommunity.com", "gamefaqs.gamespot.com",
    "pinterest.com", "discord.com",
)


def cocok_domain(host, daftar):
    return any(host == d or host.endswith("." + d) for d in daftar)


def tingkat_sumber(url):
    """Menilai tingkat kepercayaan sebuah sumber dari alamatnya: kuat, sedang, atau lemah."""
    host = (urlparse(url).hostname or "").lower()
    if cocok_domain(host, DOMAIN_LEMAH):
        return "lemah"
    if cocok_domain(host, DOMAIN_KUAT) or host.endswith(AKHIRAN_KUAT) or host.startswith("wiki."):
        return "kuat"
    return "sedang"
