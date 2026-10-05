from graf import SELESAI, Graf
from simpul.aksi import buat_aksi
from simpul.akhir import batas, jawab
from simpul.pikir import buat_pikir
from simpul.siapkan import buat_siapkan


class Agen:
    def __init__(self, klien, kotak_alat, maks_langkah):
        self.maks_langkah = maks_langkah
        self.graf = self.rakit(klien, kotak_alat)

    def rakit(self, klien, kotak_alat):
        """Menyusun simpul dan sisi. Tambah agent/simpul baru cukup di sini."""
        graf = Graf()
        graf.tambah_simpul("siapkan", buat_siapkan(kotak_alat))
        graf.tambah_simpul("pikir", buat_pikir(klien))
        graf.tambah_simpul("aksi", buat_aksi(kotak_alat))
        graf.tambah_simpul("jawab", jawab)
        graf.tambah_simpul("batas", batas)

        graf.atur_awal("siapkan")
        graf.tambah_sisi("siapkan", "pikir")
        graf.tambah_sisi_bersyarat("pikir", self.setelah_pikir)
        graf.tambah_sisi("aksi", "pikir")
        graf.tambah_sisi("jawab", SELESAI)
        graf.tambah_sisi("batas", SELESAI)

        graf.periksa()
        return graf

    def setelah_pikir(self, keadaan):
        if not keadaan["panggilan"]:
            return "jawab"
        if keadaan["putaran_llm"] >= self.maks_langkah:
            return "batas"
        return "aksi"

    def jawab(self, pertanyaan, konteks=None, riwayat=None):
        keadaan = self.graf.jalankan({"pertanyaan": pertanyaan, "konteks": konteks, "riwayat": riwayat})
        return keadaan["hasil"]