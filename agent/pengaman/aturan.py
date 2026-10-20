import base64
import codecs
import ipaddress
import re
import socket
import unicodedata
from urllib.parse import urlparse

BATAS_PERTANYAAN = 2000
BATAS_TEKS_WEB = 12000
SUMBER_BAWAAN = 2
SUMBER_TERBANYAK = 10
TAMBAHAN_DARI_MINIMAL = 3

KATA_MINTA_INTERNET = [
    "internet", "web", "online", "google", "browsing", "telusuri", "searching",
    "cari di", "carikan", "situs", "link", "url", "berita", "terbaru", "terkini",
]

POLA_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# pesan yang tidak perlu dicek ke internet dulu: sapaan, terima kasih, pertanyaan tentang diri pengguna, dan tulisan kreatif
POLA_TANPA_CARI = [re.compile(pola) for pola in (
    r"^(halo|hai|hi|hello|hey|pagi|siang|sore|malam|selamat \w+|terima ?kasih|makasih|thanks?|thank you|oke|ok|siap|mantap|sip|baik)\b[\s\w]{0,15}[!.?]*$",
    r"\b(ingat|kenal)\b.{0,15}\b(aku|saya|namaku|nama saya)\b",
    r"\bsiapa\b.{0,10}\b(aku|saya|namaku|nama saya)\b",
    r"\b(buat|buatkan|bikin|bikinkan|tulis|tuliskan|karang|karangkan)\b.{0,30}\b(cerita|cerpen|puisi|pantun|lagu|lirik|naskah|caption|ucapan|surat|dongeng)\b",
)]

POLA_KATA_SUMBER = re.compile(r"\b(sumber|referensi|rujukan|link|tautan)")
POLA_MINIMAL = re.compile(r"\b(?:minimal|minimum|min|paling sedikit|setidaknya|sedikitnya)\.?\s*(\d{1,2})\b")
POLA_MAKSIMAL = re.compile(r"\b(?:maksimal|maksimum|maks|max|paling banyak)\.?\s*(\d{1,2})\b")
POLA_JUMLAH = re.compile(r"\b(\d{1,2})\s*(?:sumber|referensi|rujukan|link|tautan)")

POLA_MERUSAK = [re.compile(pola) for pola in (
    r"\b(abaikan|lupakan|hiraukan|ignore|ignorez|ignoriere|ignora|ignorar|disregard|forget|oublie|vergiss|olvida)\b.{0,40}\b(instruksi|perintah|aturan|arahan|instructions?|rules?|prompt|anweisungen|instrucciones|istruzioni|regles|reglas)\b",
    r"\b(system[ _-]?prompt|sistem[ _-]?prompt|prompt (sistem|systeme|system|del sistema)|instruksi sistem|system instructions?)\b",
    r"(忽略|无视|忘记|忘掉).{0,20}(指示|指令|规则|提示)|系统提示|系统指令|システムプロンプト",
    r"\b(api[ _-]?key|kunci (api|akses|rahasia)|access key|secret key|password|kata sandi|token|kredensial|credentials?|secret|variabel lingkungan|environment variables?|konfigurasi)\s?(mu|kamu|anda|kalian|vokapas|milikmu|milik ?(kamu|anda))\b",
    r"\bkunci (api|akses|rahasia)\b.{0,30}\b(server|sistem|vokapas|kamu|mu|ini)\b",
    r"\byour\s+(api[ _-]?key|password|token|credentials?|secret|system prompt|prompt|instructions?|rules?|guidelines?|config\w*)\b",
    r"\b(isi|tampilkan|bacakan|print|show|cat)\b.{0,30}\.env\b",
    r"\b(sebutkan|bocorkan|beritahu|tampilkan|berikan|kasih)\b.{0,15}\brahasia\s?(mu|kamu|anda)\b",
    r"\b(aturan|pedoman|instruksi|arahan|rules?|instructions?|guidelines?)\s?(mu|kamu|anda|milikmu|rahasia|yang (kamu|anda) (terima|dapat|punya|ikuti)|yang diberikan|dari pembuat\w*|pembuatmu)\b",
    r"\b(print|repeat|show|output|tulis|ulangi|tampilkan|salin|copy|sebutkan|berikan)\b.{0,40}\b(above|before|sebelum|di atas)\b.{0,20}\b(this message|pesan ini|pesan pertama\w*|first message|percakapan)\b",
    r"\b(alat|tools?|fungsi|functions?)\b.{0,30}\b(kamu|mu|anda|you|your)\b.{0,30}\b(parameter|skema|schema|deklarasi|punya|miliki|have)\b",
    r"\b(base ?64|rot ?13|morse|caesar|hex)\b.{0,60}\b(jalankan|lakukan|ikuti|kerjakan|execute|follow|obey)\b",
    r"\b(balas|jawab|tulis|reply|answer|respond)\b.{0,20}\b(dalam|dengan|pakai|in|using)\s+(base ?64|rot ?13|morse|hex|biner|binary)\b",
    r"\b(ai|bot|asisten|kamu|mode|you)\b.{0,20}\b(tanpa (batasan|filter|sensor|aturan)|no (restrictions|rules|filter)|unrestricted|unfiltered|uncensored)\b",
    r"\b(aku|saya|i am|i'm|im)\s+(developer|pengembang|pembuat|admin\w*|owner|pemilik|creator)\s+(vokapas|kamu|mu|sistem ini|bot ini|you)\b",
    r"\b(boleh|berhak|izin|diizinkan|allowed)\b.{0,30}\b(data rahasia|semua data|secret|confidential)\b",
    r"\b(mulai sekarang|dari sekarang|seterusnya|sengaja|from now on|deliberately)\b.{0,40}\b(salah|keliru|bohong|ngawur|wrong|incorrect|lie)\b",
    r"\b(tulis|buat|buatkan|karang|bikin|write|make|create)\w*\b.{0,30}\b(sumber|referensi|rujukan|sitasi|kutipan|berita)\s+(palsu|bohongan|fiktif|fake|hoaks|hoax)\b",
    r"\b(ikuti|jalankan|lakukan|patuhi|follow|execute|obey)\b.{0,30}\b(instruksi|perintah|arahan|instructions?|commands?)\b.{0,30}\b(halaman|situs|link|web|url|page|site|di sana|di situ)\b",
    r"\b(drop|truncate)\s+(table|database)\b",
    r"\bdelete\s+from\b",
    r"\brm\s+-rf\b",
    r"\b(hapus|kosongkan|rusak|hancurkan|musnahkan)\b.{0,40}\b(database|basis data|tabel|sistem|server|algoritma|semua data|seluruh data)\b",
    r"\b(matikan|nonaktifkan|lewati|bypass)\b.{0,40}\b(pengaman|filter|batasan|aturan|guard ?rail)\b",
    r"\b(jailbreak|developer mode|mode pengembang|mode debug|debug mode|mode admin|admin mode|god mode)\b",
)]
# "DAN" (do anything now) dicek dengan huruf kapital agar kata sambung "dan" tidak ikut tertolak
POLA_DAN = re.compile(r"\bDAN\b(?!\s+[A-Z][a-z])")
POLA_BASE64 = re.compile(r"[A-Za-z0-9+/]{12,}={0,2}")
ANGKA_LEET = str.maketrans("4310572@$", "aeiostaas")

class GalatPengaman(Exception):
    pass


def periksa_pertanyaan(teks):
    teks = (teks or "").strip()
    if not teks:
        raise GalatPengaman("pertanyaan wajib diisi")
    if len(teks) > BATAS_PERTANYAAN:
        raise GalatPengaman(f"pertanyaan maksimal {BATAS_PERTANYAAN} karakter")
    return teks


def minta_internet(teks):
    """True jika pengguna jelas meminta sesuatu dari internet."""
    kecil = teks.lower()
    if POLA_URL.search(kecil):
        return True
    return any(kata in kecil for kata in KATA_MINTA_INTERNET)

def butuh_cari(teks):
    """True jika pertanyaan sebaiknya dicek ke internet dulu sebelum dijawab, agar fakta tidak diambil dari ingatan model."""
    kecil = " ".join(teks.lower().split())
    if len(kecil) < 4:
        return False
    return not any(pola.search(kecil) for pola in POLA_TANPA_CARI)

def permintaan_merusak(teks):
    """True jika pesan berusaha membatalkan aturan agent, membocorkan rahasia, atau merusak data dan sistem, termasuk yang disamarkan."""
    if POLA_DAN.search(teks):
        return True
    return any(pola.search(varian) for varian in varian_teks(teks) for pola in POLA_MERUSAK)


def varian_teks(teks):
    """Teks asli ditambah versi yang samarannya dibuka: tanpa aksen, huruf terpisah disambung, angka leet jadi huruf, ROT13, dan base64."""
    kecil = teks.lower()
    polos = "".join(h for h in unicodedata.normalize("NFKD", kecil) if not unicodedata.combining(h))
    sambung = re.sub(r"(?<=\b\w)[-._*](?=\w\b)", "", polos)
    varian = [kecil, polos, sambung, sambung.translate(ANGKA_LEET), codecs.encode(polos, "rot13")]
    for potongan in POLA_BASE64.findall(teks):
        try:
            varian.append(base64.b64decode(potongan + "=" * (-len(potongan) % 4), validate=True).decode("utf-8").lower())
        except ValueError:
            pass
    return varian


def batas_sumber(teks):
    """Membaca permintaan jumlah sumber luar dan mengembalikan (minimal, maksimal)."""
    kecil = teks.lower()
    if not POLA_KATA_SUMBER.search(kecil):
        return 0, SUMBER_BAWAAN

    minimal = angka_pertama(POLA_MINIMAL, kecil)
    maksimal = angka_pertama(POLA_MAKSIMAL, kecil)
    if minimal is None and maksimal is None:
        maksimal = angka_pertama(POLA_JUMLAH, kecil)
    if maksimal is None:
        maksimal = SUMBER_BAWAAN if minimal is None else minimal + TAMBAHAN_DARI_MINIMAL

    maksimal = max(1, min(maksimal, SUMBER_TERBANYAK))
    return min(minimal or 0, maksimal), maksimal


def angka_pertama(pola, teks):
    cocok = pola.search(teks)
    return int(cocok.group(1)) if cocok else None

def domain_diblokir(host, daftar_blokir):
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in daftar_blokir)


def periksa_url(url, daftar_blokir):
    """Menolak URL yang bukan http/https, port aneh, domain terlarang, atau mengarah ke jaringan internal."""
    bagian = urlparse(url)
    if bagian.scheme not in ("http", "https"):
        raise GalatPengaman("hanya alamat http/https yang diizinkan")
    if not bagian.hostname:
        raise GalatPengaman("alamat tidak valid")
    if bagian.port not in (None, 80, 443):
        raise GalatPengaman("port tidak diizinkan")
    if bagian.username or bagian.password:
        raise GalatPengaman("alamat berisi login tidak diizinkan")
    if domain_diblokir(bagian.hostname, daftar_blokir):
        raise GalatPengaman("domain diblokir")

    try:
        alamat_ip = {info[4][0] for info in socket.getaddrinfo(bagian.hostname, None)}
    except socket.gaierror:
        raise GalatPengaman("domain tidak ditemukan")

    for ip in alamat_ip:
        if not ipaddress.ip_address(ip.split("%")[0]).is_global:
            raise GalatPengaman("alamat jaringan internal tidak diizinkan")
    return url


def potong(teks, batas=BATAS_TEKS_WEB):
    teks = " ".join(teks.split())
    return teks if len(teks) <= batas else teks[:batas] + " ...(dipotong)"