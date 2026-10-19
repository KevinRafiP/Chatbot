from graf import SELESAI, Graf
from ingatan import ringkas
from simpul.aksi import buat_aksi
from simpul.akhir import batas, jawab, tolak
from simpul.pikir import buat_pikir
from simpul.siapkan import buat_siapkan
from simpul.verifikasi import buat_verifikasi


class Agen:
    def __init__(self, klien, kotak_alat, maks_langkah, verifikasi=True):
        self.maks_langkah = maks_langkah
        self.verifikasi = verifikasi
        self.klien = klien
        self.graf = self.rakit(klien, kotak_alat)

    def rakit(self, klien, kotak_alat):
        """Menyusun simpul dan sisi. Tambah agent/simpul baru cukup di sini."""
        graf = Graf()
        graf.tambah_simpul("siapkan", buat_siapkan(kotak_alat))
        graf.tambah_simpul("pikir", buat_pikir(klien))
        graf.tambah_simpul("aksi", buat_aksi(kotak_alat, self.maks_langkah))
        graf.tambah_simpul("verifikasi", buat_verifikasi(klien))
        graf.tambah_simpul("jawab", jawab)
        graf.tambah_simpul("batas", batas)
        graf.tambah_simpul("tolak", tolak)

        graf.atur_awal("siapkan")
        graf.tambah_sisi_bersyarat("siapkan", self.setelah_siapkan)
        graf.tambah_sisi_bersyarat("pikir", self.setelah_pikir)
        graf.tambah_sisi("aksi", "pikir")
        graf.tambah_sisi("verifikasi", "jawab")
        graf.tambah_sisi("jawab", SELESAI)
        graf.tambah_sisi("batas", SELESAI)
        graf.tambah_sisi("tolak", SELESAI)

        graf.periksa()
        return graf

    def setelah_siapkan(self, keadaan):
        return "tolak" if keadaan["ditolak"] else "pikir"

    def setelah_pikir(self, keadaan):
        if not keadaan["panggilan"]:
            return "verifikasi" if self.verifikasi else "jawab"
        if keadaan["putaran_llm"] >= self.maks_langkah:
            return "batas"
        return "aksi"

    def jawab(self, pertanyaan, konteks=None, riwayat=None, ingatan=None, kabar=None):
        """kabar(jenis, isi) dipanggil setiap ada langkah atau potongan teks baru; kosong berarti tanpa stream."""
        keadaan = self.graf.jalankan({
            "pertanyaan": pertanyaan, "konteks": konteks, "riwayat": riwayat, "ingatan": ingatan, "kabar": kabar,
        })
        return keadaan["hasil"]

    def ringkas(self, ingatan_lama, riwayat):
        """Memperbarui ingatan jangka panjang pengguna dari percakapan terbaru."""
        return ringkas(self.klien, ingatan_lama, riwayat)