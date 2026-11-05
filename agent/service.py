from graf import SELESAI, Graf
from ingatan import ringkas
from llm import pemakaian
from ringkasan import BATAS_RINGKASAN, ringkas_percakapan
from simpul.aksi import buat_aksi
from prompt import INSTRUKSI_SISTEM
from simpul.akhir import buat_batas, jawab, tolak
from simpul.periksa import buat_periksa
from simpul.pikir import buat_pikir
from simpul.siapkan import buat_siapkan
from simpul.verifikasi import verifikasi


class Agen:
    def __init__(self, klien, kotak_alat, maks_langkah, verifikasi=True, instruksi=INSTRUKSI_SISTEM, pemeriksa=None, penulis=None):
        """pemeriksa = (klien model pemeriksa, batas huruf sumber) untuk simpul periksa logika; None = tanpa pemeriksa.
        penulis(riwayat, pertanyaan) menulis ulang pesan lanjutan menjadi pertanyaan lengkap."""
        self.penulis = penulis
        self.maks_langkah = maks_langkah
        self.verifikasi = verifikasi
        self.pemeriksa = pemeriksa
        self.instruksi = instruksi
        self.klien = klien
        self.graf = self.rakit(klien, kotak_alat)

    def rakit(self, klien, kotak_alat):
        """Menyusun simpul dan sisi. Tambah agent/simpul baru cukup di sini."""
        graf = Graf()
        graf.tambah_simpul("siapkan", buat_siapkan(kotak_alat, self.penulis))
        graf.tambah_simpul("pikir", buat_pikir(klien, self.instruksi, kotak_alat.cfg.paksa_cari))
        graf.tambah_simpul("aksi", buat_aksi(kotak_alat, self.maks_langkah))
        graf.tambah_simpul("verifikasi", verifikasi)
        if self.pemeriksa:
            graf.tambah_simpul("periksa", buat_periksa(self.pemeriksa[0], klien, self.instruksi, self.pemeriksa[1]))
            graf.tambah_sisi("periksa", self.setelah_draf())
        graf.tambah_simpul("jawab", jawab)
        graf.tambah_simpul("batas", buat_batas(klien, self.instruksi))
        graf.tambah_simpul("tolak", tolak)

        graf.atur_awal("siapkan")
        graf.tambah_sisi_bersyarat("siapkan", self.setelah_siapkan)
        graf.tambah_sisi_bersyarat("pikir", self.setelah_pikir)
        graf.tambah_sisi("aksi", "pikir")
        graf.tambah_sisi("verifikasi", "jawab")
        graf.tambah_sisi("jawab", SELESAI)
        graf.tambah_sisi("batas", self.setelah_draf())
        graf.tambah_sisi("tolak", SELESAI)

        graf.periksa()
        return graf

    def setelah_siapkan(self, keadaan):
        return "tolak" if keadaan["ditolak"] else "pikir"

    def setelah_pikir(self, keadaan):
        if keadaan.get("ke_batas"):
            return "batas"
        if not keadaan["panggilan"]:
            return "periksa" if self.pemeriksa else self.setelah_draf()
        if keadaan["putaran_llm"] >= self.maks_langkah:
            return "batas"
        return "aksi"

    def setelah_draf(self):
        return "verifikasi" if self.verifikasi else "jawab"

    def jawab(self, pertanyaan, konteks=None, riwayat=None, ingatan=None, kabar=None, lampiran=None, bisa_email=False,
              ringkasan=None):
        """kabar(jenis, isi) dipanggil setiap ada langkah atau potongan teks baru; kosong berarti tanpa stream.
        lampiran {"nama", "teks"} adalah berkas dari pengguna; bisa_email True jika akun pengguna bisa menerima email.
        ringkasan adalah ringkasan pesan lama percakapan ini yang tidak lagi dikirim utuh di riwayat."""
        pemakaian.mulai()
        keadaan = self.graf.jalankan({
            "pertanyaan": pertanyaan, "konteks": konteks, "riwayat": riwayat, "ingatan": ingatan, "kabar": kabar,
            "lampiran": lampiran if isinstance(lampiran, dict) else None, "bisa_email": bisa_email is True,
            "ringkasan": str(ringkasan)[:BATAS_RINGKASAN] if isinstance(ringkasan, str) else "",
        })
        # token, jumlah panggilan model, dan alat yang dipakai dikirim ke backend untuk halaman kinerja admin
        return {**keadaan["hasil"], "kinerja": {**pemakaian.ambil(), "alat": keadaan.get("alat_dipakai", [])}}

    def ringkas(self, ingatan_lama, riwayat):
        """Memperbarui ingatan jangka panjang pengguna dari percakapan terbaru."""
        return ringkas(self.klien, ingatan_lama, riwayat)

    def ringkas_percakapan(self, ringkasan_lama, riwayat):
        """Meringkas pesan lama satu percakapan; pemakaian tokennya ikut dilaporkan."""
        pemakaian.mulai()
        teks = ringkas_percakapan(self.klien, ringkasan_lama, riwayat)
        return {"ringkasan": teks, "kinerja": {**pemakaian.ambil(), "alat": []}}