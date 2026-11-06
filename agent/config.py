import os
from dataclasses import dataclass
from pathlib import Path

from alat.sumber_utama import domain_bawaan

FOLDER_AGENT = Path(__file__).resolve().parent
# model dan kemiripan minimal bawaan per EMBED_PROVIDER; angka kemiripan masih perkiraan, sesuaikan dari log backend
MODEL_EMBED_BAWAAN = {"aws": "cohere.embed-multilingual-v3", "api": "gemini-embedding-2", "local": "bge-m3"}
SKOR_EMBED_BAWAAN = {"aws": 0.35, "api": 0.55, "local": 0.45}
MAKS_PENYEDIA_CARI = 10

@dataclass
class PengaturanAlat:
    mati: set
    agen_pengguna: str
    batas_waktu: int
    geokode_url: str
    libur_url: str
    kurs_provider: str
    kurs_url: str
    kurs_cache_detik: int
    cuaca_url: str
    salat_url: str
    salat_metode: int
    gempa_url: str
    rute_url: str
    wilayah_url: str
    game_url: str
    anime_url: str
    wikipedia_bahasa: str
    backend_url: str
    backend_api_key: str
    kalkulus_batas_detik: int
    berkas_maks_huruf: int
    pilih_otomatis: bool
    kode_runtime: list
    kode_batas_detik: int
    kode_api_url: str
    kode_api_key: str

@dataclass
class Config:
    host: str
    port: int
    api_key: str
    llm_provider: str
    aws_auth_mode: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    llm_model: str
    llm_model_cepat: str
    llm_model_tamu: str
    llm_model_cadangan: str
    api_url: str
    api_key_llm: str
    api_model: str
    local_url: str
    local_model: str
    local_api_key: str
    local_penalaran: str
    local_konteks: int
    local_batas_waktu: int
    penyedia_cari: list
    cari_jeda_detik: int
    maks_langkah: int
    maks_baca_url: int
    cepat_maks_langkah: int
    cepat_maks_baca_url: int
    tamu_maks_langkah: int
    tamu_maks_baca_url: int
    verifikasi_jawaban: bool
    periksa_logika: bool
    llm_model_periksa: str
    llm_model_tulis: str
    baca_isi_halaman: int
    baca_isi_huruf: int
    sumber_utama: dict
    tulis_batas_detik: int
    periksa_huruf_sumber: int
    wajib_cari: bool
    cari_walau_data: bool
    cepat_wajib_cari: bool
    min_sumber: int
    paksa_cari: bool
    wajib_alat: bool
    ingatan_rujukan: bool
    baca_banyak: bool
    cari_kedalaman: str
    batas_waktu: int
    domain_diblokir: list
    cache_cari_detik: int
    cache_cari_maks: int
    cuplikan_maks_huruf: int
    halaman_maks_huruf: int
    hemat_obrolan: bool
    embed_provider: str
    embed_model: str
    embed_region: str
    maks_token_jawaban: int
    riwayat_pesan: int
    riwayat_huruf_terbaru: int
    baca_gambar: bool
    model_gambar: str
    cari_gambar_penyedia: str
    saucenao_api_key: str
    saucenao_ambang: int
    saucenao_batas_detik: int
    embed_api_url: str
    embed_api_key: str
    embed_local_url: str
    embed_local_api_key: str
    embed_skor_minimal: float
    alat: PengaturanAlat


def baca_env(path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as berkas:
        for baris in berkas:
            baris = baris.strip()
            if not baris or baris.startswith("#") or "=" not in baris:
                continue
            kunci, nilai = baris.split("=", 1)
            os.environ.setdefault(kunci.strip(), nilai.strip())


def ambil(kunci, bawaan=""):
    return os.environ.get(kunci, "") or bawaan

def ambil_domain(kunci, bawaan):
    nilai = ambil(kunci).strip()
    if nilai.lower() in ("tidak", "mati"):
        return []
    return [d.strip().lower() for d in nilai.split(",") if d.strip()] or list(bawaan)

def ambil_angka(kunci, bawaan):
    try:
        nilai = int(os.environ.get(kunci, ""))
    except ValueError:
        return bawaan
    return nilai if nilai > 0 else bawaan

def ambil_desimal(kunci, bawaan):
    """Angka pecahan 0 sampai 1, contoh 0.35; selain itu memakai bawaan."""
    try:
        nilai = float(os.environ.get(kunci, ""))
    except ValueError:
        return bawaan
    return nilai if 0 <= nilai <= 1 else bawaan

def ambil_url(kunci, bawaan):
    """Alamat API dengan bawaan; diisi "mati" untuk mematikan fitur yang memakai alamat itu."""
    nilai = ambil(kunci, bawaan).strip()
    return "" if nilai.lower() in ("mati", "tidak", "off", "0") else nilai.rstrip("/")

def ambil_ya(kunci, bawaan):
    nilai = os.environ.get(kunci, "").strip().lower()
    if not nilai:
        return bawaan
    return nilai in ("1", "ya", "true", "on")

def ambil_penyedia_cari():
    """Urutan penyedia dari CARI_PENYEDIA (paling banyak 10); kunci tiap penyedia di NAMA_API_KEY, contoh exa_2 = EXA_2_API_KEY.
    Penyedia tanpa kunci dilewati."""
    daftar = []
    for nama in ambil("CARI_PENYEDIA", "tavily").lower().split(","):
        nama = nama.strip()
        kunci = ambil(f"{nama.upper()}_API_KEY")
        if nama and kunci and nama not in [n for n, _ in daftar]:
            daftar.append((nama, kunci))
    return daftar[:MAKS_PENYEDIA_CARI]

def muat():
    """Membaca .env lalu mengisi Config."""
    baca_env(FOLDER_AGENT / ".env")

    diblokir = [d.strip().lower() for d in ambil("AGENT_DOMAIN_DIBLOKIR").split(",") if d.strip()]
    
    provider = ambil("LLM_PROVIDER", "aws").lower()
    penyedia_embed = ambil("EMBED_PROVIDER").lower()
    maks_langkah = ambil_angka("AGENT_MAKS_LANGKAH", 6)
    maks_baca_url = ambil_angka("AGENT_MAKS_BACA_URL", 3)
    verifikasi = ambil_ya("AGENT_VERIFIKASI_JAWABAN", True)
    wajib_cari = ambil_ya("AGENT_WAJIB_CARI", True)
    paksa_cari = False
    baca_banyak = False
    wajib_alat = False
    cari_walau_data = ambil_ya("AGENT_CARI_WALAU_ADA_DATA", False)
    cepat_wajib_cari = ambil_ya("CEPAT_WAJIB_CARI", False)
    model_cepat, model_tamu, model_cadangan = ambil("LLM_MODEL_CEPAT"), ambil("LLM_MODEL_TAMU"), ambil("LLM_MODEL_CADANGAN")
    model_periksa, model_gambar = ambil("LLM_MODEL_PERIKSA"), ambil("LLM_MODEL_GAMBAR")
    model_tulis = ambil("LLM_MODEL_TULIS_ULANG")
    if provider == "local":
        # model di laptop lebih lambat, jadi jumlah langkah dan halaman yang dibaca dibatasi tersendiri
        maks_langkah = ambil_angka("LOCAL_MAKS_LANGKAH", 3)
        maks_baca_url = ambil_angka("LOCAL_MAKS_BACA_URL", 1)
        # verifikasi tanpa LLM (hanya mencocokkan angka dan sitasi dengan sumber), jadi tetap aktif di model lokal
        verifikasi = ambil_ya("LOCAL_VERIFIKASI_JAWABAN", True)
        wajib_cari = ambil_ya("LOCAL_WAJIB_CARI", True)
        # model lokal sering mengarang dari ingatannya sendiri, jadi pertanyaan fakta tetap dicari walau ada data internal, juga di mode cepat
        cari_walau_data = ambil_ya("LOCAL_CARI_WALAU_ADA_DATA", True)
        cepat_wajib_cari = ambil_ya("LOCAL_CEPAT_WAJIB_CARI", True)
        # Ollama mengabaikan "wajib memakai alat", jadi agent sendiri yang memastikan cari_web dipanggil
        paksa_cari = ambil_ya("LOCAL_PAKSA_CARI", True)
        # pertanyaan hitungan, tanggal, kurs, atau lokasi wajib memakai alat walau ada data internal
        wajib_alat = ambil_ya("LOCAL_WAJIB_ALAT", True)
        # model lokal tidak membayar token, jadi mode mendalam diminta membuka beberapa halaman, bukan hanya cuplikan
        baca_banyak = ambil_ya("LOCAL_BACA_BANYAK", True)
        # nama model AWS tidak dikenal Ollama, jadi model tambahan dibaca dari LOCAL_MODEL_*; kosong = LOCAL_MODEL
        model_cepat, model_tamu, model_cadangan = ambil("LOCAL_MODEL_CEPAT"), ambil("LOCAL_MODEL_TAMU"), ambil("LOCAL_MODEL_CADANGAN")
        model_periksa, model_gambar = ambil("LOCAL_MODEL_PERIKSA"), ambil("LOCAL_MODEL_GAMBAR")
        model_tulis = ambil("LOCAL_MODEL_TULIS_ULANG")

    kurs_provider = "exchangerate" if ambil("KURS_PROVIDER", "frankfurter").lower() == "exchangerate" else "frankfurter"
    alat = PengaturanAlat(
        # nama alat dipisah koma, contoh ALAT_MATI=info_hiburan,kalkulus
        mati={n.strip().lower() for n in ambil("ALAT_MATI").split(",") if n.strip()},
        agen_pengguna=ambil("ALAT_USER_AGENT", "Vokapas/1.0 (chatbot)"),
        batas_waktu=ambil_angka("AGENT_BATAS_WAKTU_DETIK", 15),
        geokode_url=ambil_url("GEOKODE_API_URL", "https://geocoding-api.open-meteo.com/v1"),
        libur_url=ambil_url("LIBUR_API_URL", "https://date.nager.at/api/v3"),
        kurs_provider=kurs_provider,
        kurs_url=ambil_url("KURS_API_URL", "https://open.er-api.com/v6" if kurs_provider == "exchangerate" else "https://api.frankfurter.dev/v1"),
        kurs_cache_detik=ambil_angka("KURS_CACHE_MENIT", 60) * 60,
        cuaca_url=ambil_url("CUACA_API_URL", "https://api.open-meteo.com/v1"),
        salat_url=ambil_url("SALAT_API_URL", "https://api.aladhan.com/v1"),
        # 20 = Kementerian Agama RI di Aladhan
        salat_metode=ambil_angka("SALAT_METODE", 20),
        gempa_url=ambil_url("GEMPA_API_URL", "https://data.bmkg.go.id/DataMKG/TEWS"),
        rute_url=ambil_url("RUTE_API_URL", "https://router.project-osrm.org"),
        wilayah_url=ambil_url("WILAYAH_API_URL", "https://wilayah.id/api"),
        game_url=ambil_url("GAME_API_URL", "https://www.cheapshark.com/api/1.0"),
        anime_url=ambil_url("ANIME_API_URL", "https://api.jikan.moe/v4"),
        wikipedia_bahasa="" if ambil("WIKIPEDIA_BAHASA", "id").lower() in ("mati", "tidak") else ambil("WIKIPEDIA_BAHASA", "id").lower(),
        # backend di container yang sama; kosong = alat cari_pengetahuan mati
        backend_url=ambil_url("BACKEND_URL", ""),
        backend_api_key=ambil("BACKEND_API_KEY", ambil("AGENT_API_KEY")),
        kalkulus_batas_detik=ambil_angka("KALKULUS_BATAS_DETIK", 10),
        berkas_maks_huruf=ambil_angka("BERKAS_MAKS_HURUF", 20000),
        # alat khusus (waktu, kurs, keuangan, dan lainnya) hanya dikirim ke model jika pertanyaannya cocok, agar token hemat
        pilih_otomatis=ambil_ya("ALAT_SESUAI_PERTANYAAN", True),
        # tempat menjalankan kode Python dari model, dipisah koma sesuai urutan; kosong = alat jalankan_python mati
        kode_runtime=[n.strip().lower() for n in ambil("KODE_RUNTIME").split(",") if n.strip()],
        kode_batas_detik=ambil_angka("KODE_BATAS_DETIK", 15),
        kode_api_url=ambil_url("KODE_API_URL", ""),
        kode_api_key=ambil("KODE_API_KEY"),
    )  

    return Config(
        host=ambil("AGENT_HOST", "127.0.0.1"),
        port=ambil_angka("AGENT_PORT", ambil_angka("PORT", 8082)),
        api_key=ambil("AGENT_API_KEY"),
        llm_provider=provider,
        aws_auth_mode=ambil("AWS_AUTH_MODE", "iam").lower(),
        aws_access_key_id=ambil("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=ambil("AWS_SECRET_ACCESS_KEY"),
        # samakan dengan OLLAMA_CONTEXT_LENGTH di laptop; 0 = prompt tidak dipangkas agent
        local_konteks=0 if ambil("LOCAL_KONTEKS_TOKEN") == "0" else ambil_angka("LOCAL_KONTEKS_TOKEN", 32768),
        aws_region=ambil("AWS_REGION", "ap-southeast-3"),
        llm_model=ambil("LLM_MODEL"),
        llm_model_cepat=model_cepat,
        llm_model_tamu=model_tamu,
        llm_model_cadangan=model_cadangan,
        api_url=ambil("API_URL"),
        api_key_llm=ambil("API_KEY"),
        api_model=ambil("API_MODEL"),
        local_url=ambil("LOCAL_URL", "http://127.0.0.1:11434/v1"),
        local_model=ambil("LOCAL_MODEL"),
        local_api_key=ambil("LOCAL_API_KEY"),
        local_penalaran=ambil("LOCAL_PENALARAN"),
        local_batas_waktu=ambil_angka("LOCAL_BATAS_WAKTU_DETIK", 180),
        penyedia_cari=ambil_penyedia_cari(),
        # penyedia yang kreditnya habis dicoba lagi setelah jeda ini
        cari_jeda_detik=ambil_angka("CARI_JEDA_HABIS_MENIT", 60) * 60,
        maks_langkah=maks_langkah,
        maks_baca_url=maks_baca_url,
        cepat_maks_langkah=ambil_angka("CEPAT_MAKS_LANGKAH", 3),
        cepat_maks_baca_url=ambil_angka("CEPAT_MAKS_BACA_URL", 1),
        tamu_maks_langkah=ambil_angka("TAMU_MAKS_LANGKAH", 2),
        tamu_maks_baca_url=ambil_angka("TAMU_MAKS_BACA_URL", 1),
        verifikasi_jawaban=verifikasi,
        # model cepat memeriksa logika draf jawaban mode mendalam; ada masalah = model utama menulis ulang sekali
        periksa_logika=ambil_ya("AGENT_PERIKSA_LOGIKA", provider != "local"),
        # kosong = LLM_MODEL_CEPAT (atau LLM_MODEL jika itu juga kosong)
        llm_model_periksa=model_periksa,
        # penulis ulang pertanyaan lanjutan; kosong = LLM_MODEL (atau LOCAL_MODEL); lewat batas waktu = pakai pola kata
        llm_model_tulis=model_tulis,
        # halaman teratas hasil cari_web yang dibuka otomatis (minimal 1), dan panjang bagian relevan per halaman
        baca_isi_halaman=ambil_angka("CARI_BACA_ISI", 3),
        baca_isi_huruf=ambil_angka("CARI_ISI_HURUF", 2000),
        # domain yang diutamakan per topik; isi "tidak" untuk mematikan satu topik
        sumber_utama={topik: ambil_domain(f"SUMBER_UTAMA_{topik.upper()}", domain) for topik, domain in domain_bawaan().items()},
        tulis_batas_detik=ambil_angka("TULIS_ULANG_BATAS_DETIK", 20),
        periksa_huruf_sumber=ambil_angka("AGENT_PERIKSA_HURUF_SUMBER", 12000),
        wajib_cari=wajib_cari,
        cari_walau_data=cari_walau_data,
        cepat_wajib_cari=cepat_wajib_cari,
        # minimal sumber luar untuk pertanyaan fakta jika pengguna tidak menyebut jumlahnya; 0 = tanpa minimal
        min_sumber=0 if ambil("AGENT_MIN_SUMBER") == "0" else ambil_angka("AGENT_MIN_SUMBER", 4),
        cari_kedalaman="basic" if ambil("CARI_KEDALAMAN", ambil("TAVILY_KEDALAMAN", "advanced")).lower() == "basic" else "advanced",
        batas_waktu=ambil_angka("AGENT_BATAS_WAKTU_DETIK", 15),
        domain_diblokir=diblokir,
        # CACHE_CARI=tidak mematikan cache hasil pencarian
        cache_cari_detik=ambil_angka("CACHE_CARI_JAM", 24) * 3600 if ambil_ya("CACHE_CARI", True) else 0,
        cache_cari_maks=ambil_angka("CACHE_CARI_MAKS", 500),
        # panjang teks hasil alat yang dibaca model; bukti sumber tetap menyimpan teks lengkapnya
        cuplikan_maks_huruf=ambil_angka("AGENT_MAKS_HURUF_CUPLIKAN", 1000),
        halaman_maks_huruf=ambil_angka("AGENT_MAKS_HURUF_HALAMAN", 8000),
        # sapaan dan ucapan terima kasih dijawab tanpa alat dan dengan instruksi pendek
        paksa_cari=paksa_cari,
        wajib_alat=wajib_alat,
        # ya = minat atau proyek di ingatan hanya dipakai jika pertanyaan merujuk percakapan sebelumnya ("yang tadi", "lanjutkan")
        ingatan_rujukan=ambil_ya("AGENT_INGATAN_RUJUKAN", True),
        baca_banyak=baca_banyak,
        hemat_obrolan=ambil_ya("AGENT_HEMAT_OBROLAN", True),
        # pencarian makna pengetahuan; EMBED_PROVIDER kosong = mati
        embed_provider=penyedia_embed,
        embed_model=ambil("EMBED_MODEL", MODEL_EMBED_BAWAAN.get(penyedia_embed, "")),
        embed_region=ambil("EMBED_REGION", ambil("AWS_REGION", "ap-southeast-3")),
        embed_api_url=ambil("EMBED_API_URL", "https://generativelanguage.googleapis.com/v1beta"),
        embed_api_key=ambil("EMBED_API_KEY", ambil("API_KEY")),
        # bawaannya ikut LOCAL_URL dan LOCAL_API_KEY, jadi gerbang local dan ngrok yang sama bisa dipakai
        embed_local_url=ambil("EMBED_LOCAL_URL", ambil("LOCAL_URL", "http://127.0.0.1:11434/v1")),
        # batas keluaran model per jawaban, termasuk proses berpikir; Kimi K2.5 di Bedrock paling banyak 16000
        maks_token_jawaban=ambil_angka("AGENT_MAKS_TOKEN_JAWABAN", 16000),
        # jumlah pesan sebelumnya yang dibaca model, dan panjang maksimal 2 pesan terakhir (jawaban panjang tetap terbaca awal dan akhirnya)
        riwayat_pesan=ambil_angka("AGENT_RIWAYAT_PESAN", 20),
        riwayat_huruf_terbaru=ambil_angka("AGENT_RIWAYAT_HURUF_TERBARU", 4000),
        # foto soal atau rumus dibaca model vision menjadi teks dan LaTeX; fotonya sendiri tidak disimpan
        baca_gambar=ambil_ya("BACA_GAMBAR", True),
        # kosong = LLM_MODEL; model harus bisa membaca gambar
        model_gambar=model_gambar,
        # asal foto anime, game, atau ilustrasi dicari dulu sebelum dibaca model; kosong atau mati = langsung dibaca model
        cari_gambar_penyedia=ambil("CARI_GAMBAR_PENYEDIA").lower(),
        saucenao_api_key=ambil("SAUCENAO_API_KEY"),
        # kemiripan minimal (persen) agar hasil SauceNAO dipakai; di bawahnya foto dibaca model
        saucenao_ambang=min(ambil_angka("SAUCENAO_AMBANG", 80), 100),
        saucenao_batas_detik=ambil_angka("SAUCENAO_BATAS_DETIK", 8),
        embed_local_api_key=ambil("EMBED_LOCAL_API_KEY", ambil("LOCAL_API_KEY")),
        embed_skor_minimal=ambil_desimal("EMBED_SKOR_MINIMAL", SKOR_EMBED_BAWAAN.get(penyedia_embed, 0.5)),
        alat=alat,
    )