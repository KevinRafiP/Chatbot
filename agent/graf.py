import logging

SELESAI = "__selesai__"


class GalatGraf(Exception):
    pass


class Graf:
    def __init__(self, maks_langkah=30):
        self.simpul = {}
        self.sisi = {}
        self.awal = None
        self.maks_langkah = maks_langkah # default 30 langkah, agar graph tidak looping

    def tambah_simpul(self, nama, fungsi):
        if nama in self.simpul:
            raise GalatGraf(f"simpul/node {nama} sudah ada")
        self.simpul[nama] = fungsi

    def tambah_sisi(self, dari, ke):
        self.sisi[dari] = ke

    def tambah_sisi_bersyarat(self, dari, pemilih):
        self.sisi[dari] = pemilih

    def atur_awal(self, nama):
        self.awal = nama

    def periksa(self):
        """Memastikan graf tersambung dengan benar sebelum dipakai."""
        if self.awal not in self.simpul:
            raise GalatGraf("simpul awal belum diatur atau tidak ada")
        for nama in self.simpul:
            if nama not in self.sisi:
                raise GalatGraf(f"simpul {nama} tidak punya sisi keluar")
            tujuan = self.sisi[nama]
            if isinstance(tujuan, str) and tujuan != SELESAI and tujuan not in self.simpul:
                raise GalatGraf(f"sisi {nama} -> {tujuan} menuju simpul yang tidak ada")

    def jalankan(self, keadaan):
        """Menjalankan simpul satu per satu mengikuti sisi sampai SELESAI."""
        sekarang = self.awal
        jejak = []

        while sekarang != SELESAI:
            if len(jejak) >= self.maks_langkah:
                raise GalatGraf("graf berjalan terlalu lama")
            if sekarang not in self.simpul:
                raise GalatGraf(f"simpul {sekarang} tidak ada")

            jejak.append(sekarang)
            keadaan = self.simpul[sekarang](keadaan)

            tujuan = self.sisi[sekarang]
            sekarang = tujuan(keadaan) if callable(tujuan) else tujuan

        logging.info("jejak graf: %s", " -> ".join(jejak))
        keadaan["jejak"] = jejak
        return keadaan