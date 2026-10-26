import logging
import re

from alat.acak import AlatAcak
from alat.hiburan import AlatHiburan
from alat.jaringan import GalatAlat
from alat.kalkulus import AlatKalkulus, sympy_tersedia
from alat.keuangan import AlatKeuangan
from alat.konversi import AlatKonversi
from alat.lokasi import AlatLokasi
from alat.pengetahuan import AlatPengetahuan
from alat.waktu import AlatWaktu
from alat.wikipedia import AlatWikipedia


def deklarasi(nama, deskripsi, properti, wajib=()):
    return {"name": nama, "description": deskripsi,
            "parameters": {"type": "object", "properties": properti, "required": list(wajib)}}


def teks(keterangan, pilihan=None):
    isi = {"type": "string", "description": keterangan}
    if pilihan:
        isi["enum"] = list(pilihan)
    return isi


def angka(keterangan):
    return {"type": "number", "description": keterangan}


def daftar(keterangan):
    return {"type": "array", "items": {"type": "string"}, "description": keterangan}


DEKLARASI = {
    "waktu_tanggal": deklarasi(
        "waktu_tanggal",
        "Jam sekarang di kota atau zona mana pun, konversi jam antar zona, selisih tanggal, tanggal sekian hari/bulan lagi, "
        "info hari dari sebuah tanggal, umur, dan hari libur nasional. Pakai ini, jangan menebak tanggal atau jam.",
        {"aksi": teks("Jenis perhitungan", ("sekarang", "konversi", "selisih", "tambah", "info", "umur", "libur")),
         "lokasi": daftar("Untuk aksi sekarang: kota, negara, singkatan (WIB, WITA, WIT), atau UTC+7"),
         "waktu": teks("Untuk konversi: YYYY-MM-DD HH:MM atau HH:MM"),
         "dari": teks("Zona asal untuk konversi, atau tanggal awal untuk selisih (YYYY-MM-DD)"),
         "ke": daftar("Zona tujuan untuk konversi"),
         "sampai": teks("Tanggal akhir untuk selisih atau umur; kosong = hari ini"),
         "tanggal": teks("YYYY-MM-DD untuk tambah, info, atau tanggal lahir untuk umur"),
         "jumlah": angka("Untuk tambah: jumlah yang ditambahkan, negatif untuk mundur"),
         "satuan": teks("Untuk tambah", ("hari", "minggu", "bulan", "tahun", "jam", "menit")),
         "tahun": angka("Untuk libur"), "bulan": angka("Untuk libur, opsional 1-12"),
         "negara": teks("Kode negara 2 huruf untuk libur, bawaan ID")},
        ("aksi",)),
            "konversi": deklarasi(
        "konversi",
        "Konversi mata uang dengan kurs terbaru (bisa beserta riwayat kurs untuk grafik) dan konversi satuan "
        "(panjang, berat, suhu, luas, volume, kecepatan, data, waktu, energi, tekanan).",
        {"jenis": teks("mata_uang atau satuan", ("mata_uang", "satuan")),
         "nilai": angka("Jumlah atau nilai yang dikonversi"),
         "dari": teks("Kode mata uang (USD) atau satuan asal (km, kg, c, ons)"),
         "ke": daftar("Kode mata uang tujuan, atau satu satuan tujuan"),
         "riwayat_hari": angka("Opsional untuk mata uang: ambil kurs harian sekian hari terakhir (maks 366)")},
        ("jenis", "dari", "ke")),
    "keuangan": deklarasi(
        "keuangan",
        "Hitungan keuangan yang tepat: cicilan kredit/KPR (anuitas atau flat), bunga majemuk/investasi, zakat (maal, "
        "penghasilan, fitrah), dan perkiraan PPh 21 setahun. Angka dalam rupiah tanpa titik pemisah.",
        {"jenis": teks("Jenis hitungan", ("cicilan", "bunga_majemuk", "zakat", "pph21")),
         "pokok": angka("cicilan: jumlah pinjaman"), "bunga_tahunan_persen": angka("cicilan/bunga_majemuk: bunga per tahun, contoh 7.5"),
         "tenor_bulan": angka("cicilan: lama pinjaman dalam bulan"), "metode": teks("cicilan", ("anuitas", "flat")),
         "modal": angka("bunga_majemuk: modal awal"), "tahun": angka("bunga_majemuk: lama dalam tahun"),
         "setoran_bulanan": angka("bunga_majemuk: setoran tiap bulan"),
         "jenis_zakat": teks("zakat", ("maal", "penghasilan", "fitrah")), "jumlah": angka("zakat: harta atau penghasilan per bulan"),
         "harga_emas_per_gram": angka("zakat: harga emas untuk nisab"), "jumlah_jiwa": angka("zakat fitrah"),
         "harga_beras_per_kg": angka("zakat fitrah"),
         "gaji_bruto_bulanan": angka("pph21"), "status_kawin": teks("pph21: ya atau tidak"),
         "tanggungan": angka("pph21: 0 sampai 3"), "iuran_pensiun_bulanan": angka("pph21: iuran JHT dan JP pegawai per bulan")},
        ("jenis",)),
    "kalkulus": deklarasi(
        "kalkulus",
        "Matematika simbolik: turunan, integral (tak tentu atau tentu), limit, menyelesaikan persamaan, faktorkan, jabarkan, "
        "sederhanakan. Tulis ekspresi seperti x^2 + 3*x, sin(x)/x, x^2 - 4 = 0.",
        {"operasi": teks("Operasi", ("turunan", "integral", "limit", "selesaikan", "faktorkan", "jabarkan", "sederhanakan")),
         "ekspresi": teks("Ekspresi atau persamaan"), "variabel": teks("Variabel, bawaan x"),
         "orde": angka("turunan ke berapa"), "batas_bawah": teks("integral tentu"), "batas_atas": teks("integral tentu"),
         "menuju": teks("limit: nilai yang didekati, boleh oo untuk tak hingga"), "arah": teks("limit", ("kiri", "kanan"))},
        ("operasi", "ekspresi")),
    "acak": deklarasi(
        "acak",
        "Hasil acak yang adil: angka acak, lempar dadu atau koin, memilih/mengundi dari daftar, mengacak urutan, dan membuat kata sandi.",
        {"jenis": teks("Jenis", ("angka", "dadu", "koin", "pilih", "urutan", "kata_sandi")),
         "min": angka("angka: batas bawah"), "max": angka("angka: batas atas"), "jumlah": angka("berapa hasil, bawaan 1"),
         "sisi": angka("dadu: jumlah sisi"), "pilihan": daftar("pilih/urutan: daftar pilihan"),
         "panjang": angka("kata_sandi: 8 sampai 64"), "simbol": {"type": "boolean", "description": "kata_sandi: pakai simbol"}},
        ("jenis",)),
    "info_lokasi": deklarasi(
        "info_lokasi",
        "Data tempat: prakiraan cuaca 1-7 hari, jadwal salat, gempa terbaru dari BMKG, jarak dan waktu tempuh antarkota, "
        "daftar wilayah Indonesia (provinsi, kabupaten/kota, kecamatan, kelurahan), dan koordinat.",
        {"jenis": teks("Jenis data", ("cuaca", "salat", "gempa", "jarak", "wilayah", "koordinat")),
         "tempat": teks("cuaca/salat/koordinat: nama kota, boleh ditambah provinsi, contoh Bandung, Jawa Barat"),
         "hari": angka("cuaca: jumlah hari 1-7"), "tanggal": teks("salat: YYYY-MM-DD, kosong = hari ini"),
         "daftar": teks("gempa", ("terbaru", "terkini", "dirasakan")),
         "dari": teks("jarak: kota asal"), "ke": teks("jarak: kota tujuan"),
         "provinsi": teks("wilayah: kosong = daftar provinsi"), "kota": teks("wilayah: kabupaten atau kota"),
         "kecamatan": teks("wilayah")},
        ("jenis",)),
    "info_hiburan": deklarasi(
        "info_hiburan",
        "Harga dan diskon game PC di berbagai toko (Steam, GOG, dll.), serta info anime/manga dari MyAnimeList (skor, episode, "
        "studio, sinopsis) dan daftar anime musim ini.",
        {"jenis": teks("Jenis", ("harga_game", "anime", "manga", "anime_musim_ini")), "judul": teks("Judul game, anime, atau manga")},
        ("jenis",)),
    "wikipedia": deklarasi(
        "wikipedia",
        "Ringkasan artikel Wikipedia untuk fakta umum (tokoh, tempat, sejarah, sains, istilah). Lebih cepat daripada cari_web; "
        "pakai cari_web untuk berita, harga, atau hal yang sangat baru.",
        {"topik": teks("Nama topik atau judul artikel"), "bahasa": teks("Kode bahasa Wikipedia", ("id", "en", "ja", "ms", "jv", "su"))},
        ("topik",)),
    "cari_pengetahuan": deklarasi(
        "cari_pengetahuan",
        "Mencari lagi di data internal dengan kata kunci lain jika data internal di pesan belum menjawab pertanyaan.",
        {"kueri": teks("Kata kunci singkat, misalnya nama orang, produk, atau istilah")},
        ("kueri",)),
    "kirim_email": deklarasi(
        "kirim_email",
        "Mengirim ringkasan atau jawaban ke email akun pengguna sendiri. Hanya pakai jika pengguna jelas meminta dikirim ke email.",
        {"subjek": teks("Subjek email, singkat"), "isi": teks("Isi email dalam teks biasa atau Markdown")},
        ("subjek", "isi")),
}

KETERANGAN = {
    "waktu_tanggal": "Menghitung waktu", "konversi": "Mengonversi", "keuangan": "Menghitung keuangan", "kalkulus": "Menghitung kalkulus",
    "acak": "Mengacak", "info_lokasi": "Mengambil data lokasi", "info_hiburan": "Mencari info hiburan", "wikipedia": "Membaca Wikipedia",
    "cari_pengetahuan": "Mencari data", "kirim_email": "Menyiapkan email",
}
MAKS_ISI_EMAIL = 20_000

# kata yang membuat alat khusus ikut dikirim ke model; alat yang tidak ada di sini (wikipedia, cari_pengetahuan) selalu dikirim
POLA_ALAT = {nama: re.compile(pola, re.IGNORECASE) for nama, pola in {
    "waktu_tanggal": r"\b(jam|pukul|zona|wib|wita|wit|utc|gmt|tanggal|hari apa|hari ini|besok|kemarin|lusa|minggu depan|bulan depan|"
                     r"tahun depan|berapa hari|selisih|umur|usia|lahir|libur|cuti bersama|kalender|weton|time|date|holiday|age)\b",
    "konversi": r"\b(kurs|nilai tukar|mata uang|konversi|ubah ke|jadi berapa|dolar|dollar|euro|yen|ringgit|rupiah|won|yuan|baht|peso|"
                r"usd|eur|jpy|sgd|myr|idr|gbp|aud|cny|krw|thb|sar|satuan|meter|km|cm|mm|mil|mile|inci|inch|kaki|feet|kilo|kg|gram|ons|pon|lb|"
                r"liter|ml|galon|celsius|fahrenheit|kelvin|derajat|mph|knot|hektar|byte|kb|mb|gb|tb|kalori|joule|psi|currency|convert)\b",
    "keuangan": r"\b(cicilan|kredit|kpr|pinjam\w*|utang|hutang|bunga|investasi|tabungan|nabung|menabung|deposito|majemuk|zakat|nisab|fitrah|"
                r"pajak|pph|gaji|tenor|anuitas|angsuran|dp|loan|interest|mortgage|tax)\b",
    "kalkulus": r"\b(turunan|integral|limit|derivatif|diferensial|persamaan|faktorkan|jabarkan|sederhanakan|selesaikan|solve|kuadrat|polinom\w*|"
                r"aljabar|sin|cos|tan|log|ln|dx)\b|\^|[a-z]\s*=",
    "acak": r"\b(acak|random|undi|undian|kocok|dadu|koin|lempar|pilihkan|pilih satu|kata sandi|sandi|password|shuffle)\b",
    "info_lokasi": r"\b(cuaca|hujan|panas|suhu|prakiraan|ramalan|weather|salat|shalat|sholat|solat|imsak|subuh|zuhur|dzuhur|ashar|asar|magrib|"
                   r"maghrib|isya|adzan|azan|gempa|bmkg|tsunami|jarak|rute|perjalanan|tempuh|provinsi|kabupaten|kota|kecamatan|kelurahan|desa|"
                   r"wilayah|koordinat|lokasi|letak|peta)\b",
    "info_hiburan": r"\b(anime|manga|myanimelist|mal|musim ini|season|game|gim|steam|gog|diskon|donghua|manhwa|light novel)\b",
}.items()}

class AlatTambahan:
    """Alat selain cari_web, baca_url, dan hitung; setiap alat bisa dimatikan lewat ALAT_MATI di .env."""

    def __init__(self, p):
        self.p = p
        self.alat = {}
        calon = {
            "waktu_tanggal": lambda: AlatWaktu(p), "konversi": lambda: AlatKonversi(p), "keuangan": AlatKeuangan,
            "kalkulus": lambda: AlatKalkulus(p) if sympy_tersedia() else None, "acak": AlatAcak,
            "info_lokasi": lambda: AlatLokasi(p), "info_hiburan": lambda: AlatHiburan(p) if p.game_url or p.anime_url else None,
            "wikipedia": lambda: AlatWikipedia(p) if p.wikipedia_bahasa else None,
            "cari_pengetahuan": lambda: AlatPengetahuan(p) if p.backend_url else None,
            "kirim_email": lambda: "email",
        }
        for nama, buat in calon.items():
            if nama in p.mati:
                continue
            alat = buat()
            if alat is None:
                logging.info("alat %s tidak aktif (paket atau alamat API belum diatur)", nama)
                continue
            self.alat[nama] = alat

    def deklarasi(self, email=False, teks=None):
        """teks berisi pertanyaan dan pesan terakhir pengguna; None berarti semua alat dikirim."""
        hasil = []
        for nama in self.alat:
            if nama == "kirim_email" and not email:
                continue
            pola = POLA_ALAT.get(nama)
            if teks is not None and self.p.pilih_otomatis and pola and not pola.search(teks):
                continue
            hasil.append(DEKLARASI[nama])
        return hasil

    def punya(self, nama):
        return nama in self.alat

    def keterangan(self, nama):
        return KETERANGAN.get(nama, "Menjalankan alat")

    def jalankan(self, nama, argumen, catatan, tambah_sumber):
        alat = self.alat[nama]
        try:
            if nama in ("info_lokasi", "info_hiburan", "wikipedia"):
                return alat.jalankan(argumen, catatan, tambah_sumber)
            if nama == "cari_pengetahuan":
                return alat.jalankan(argumen, catatan)
            if nama == "kirim_email":
                return siapkan_email(argumen, catatan)
            return alat.jalankan(argumen)
        except GalatAlat as galat:
            return {"galat": str(galat)}
        except (ValueError, TypeError, ArithmeticError, KeyError) as galat:
            logging.info("alat %s menolak masukan: %s", nama, galat)
            return {"galat": f"masukan tidak valid: {str(galat)[:200]}"}


def siapkan_email(argumen, catatan):
    """Email tidak dikirim di agent; backend yang mengirimnya ke alamat akun setelah jawaban selesai."""
    if not catatan.get("bisa_email"):
        return {"galat": "email hanya bisa dikirim untuk akun yang emailnya sudah terverifikasi"}
    subjek = " ".join(str(argumen.get("subjek") or "").split())[:150]
    isi = str(argumen.get("isi") or "").strip()[:MAKS_ISI_EMAIL]
    if not subjek or not isi:
        return {"galat": "subjek dan isi wajib diisi"}
    catatan["email"] = {"subjek": subjek, "isi": isi}
    return {"status": "akan dikirim ke email akun pengguna setelah jawaban ini selesai"}