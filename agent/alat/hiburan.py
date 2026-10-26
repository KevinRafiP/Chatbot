from alat.jaringan import CacheSingkat, GalatAlat, ambil_json

cache_toko = CacheSingkat(24 * 3600, 2)
cache_hiburan = CacheSingkat(30 * 60, 200)


class AlatHiburan:
    def __init__(self, p):
        self.p = p

    def jalankan(self, argumen, catatan, tambah_sumber):
        jenis = str(argumen.get("jenis", "")).lower()
        judul = " ".join(str(argumen.get("judul") or "").split())[:100]
        if jenis == "harga_game":
            return self.harga_game(judul, catatan, tambah_sumber)
        if jenis in ("anime", "manga"):
            return self.anime(jenis, judul, catatan, tambah_sumber)
        if jenis == "anime_musim_ini":
            return self.musim_ini(catatan, tambah_sumber)
        raise GalatAlat("jenis harus harga_game, anime, manga, atau anime_musim_ini")

    def ambil(self, alamat, parameter=None):
        kunci = f"{alamat}?{sorted((parameter or {}).items())}"
        return cache_hiburan.ambil_atau_buat(kunci, lambda: ambil_json(alamat, parameter, self.p.batas_waktu, self.p.agen_pengguna))

    def harga_game(self, judul, catatan, tambah_sumber):
        if not self.p.game_url:
            raise GalatAlat("harga game tidak aktif")
        if not judul:
            raise GalatAlat("judul game wajib diisi")
        hasil = self.ambil(f"{self.p.game_url}/games", {"title": judul, "limit": 3})
        if not hasil:
            raise GalatAlat(f"game {judul} tidak ditemukan di CheapShark (hanya game PC)")
        toko = {t["storeID"]: t["storeName"] for t in cache_toko.ambil_atau_buat(
            "toko", lambda: ambil_json(f"{self.p.game_url}/stores", None, self.p.batas_waktu, self.p.agen_pengguna))}
        daftar = []
        for game in hasil[:3]:
            rinci = self.ambil(f"{self.p.game_url}/games", {"id": game["gameID"]})
            penawaran = sorted(rinci.get("deals") or [], key=lambda d: float(d.get("price", 0)))[:5]
            termurah = rinci.get("cheapestPriceEver") or {}
            daftar.append({
                "judul": (rinci.get("info") or {}).get("title") or game.get("external"),
                "penawaran": [{
                    "toko": toko.get(d.get("storeID"), d.get("storeID")), "harga_usd": d.get("price"),
                    "harga_normal_usd": d.get("retailPrice"), "diskon_persen": round(float(d.get("savings") or 0)),
                    "link": f"https://www.cheapshark.com/redirect?dealID={d.get('dealID')}",
                } for d in penawaran],
                "termurah_sepanjang_masa_usd": termurah.get("price"),
            })
        nomor = tambah_sumber(catatan, f"Harga {judul} - CheapShark", f"https://www.cheapshark.com/search#q:{judul.replace(' ', '%20')}", "")
        return {"game": daftar, "nomor": nomor,
                "catatan": "Harga dalam USD dari toko PC (Steam, GOG, dan lainnya); harga Steam Indonesia dalam rupiah bisa berbeda."}

    def anime(self, jenis, judul, catatan, tambah_sumber):
        if not self.p.anime_url:
            raise GalatAlat("info anime tidak aktif")
        if not judul:
            raise GalatAlat("judul wajib diisi")
        data = self.ambil(f"{self.p.anime_url}/{jenis}", {"q": judul, "limit": 3, "sfw": "true"})
        daftar = [ringkas_anime(item, jenis) for item in (data.get("data") or [])[:3]]
        if not daftar:
            raise GalatAlat(f"{jenis} {judul} tidak ditemukan")
        nomor = tambah_sumber(catatan, f"{daftar[0]['judul']} - MyAnimeList", daftar[0]["url"], daftar[0].get("sinopsis", ""))
        return {jenis: daftar, "nomor": nomor, "catatan": "Data MyAnimeList lewat Jikan; skor bisa berubah."}

    def musim_ini(self, catatan, tambah_sumber):
        if not self.p.anime_url:
            raise GalatAlat("info anime tidak aktif")
        data = self.ambil(f"{self.p.anime_url}/seasons/now", {"limit": 15, "sfw": "true"})
        daftar = [ringkas_anime(item, "anime", singkat=True) for item in (data.get("data") or [])[:15]]
        nomor = tambah_sumber(catatan, "Anime musim ini - MyAnimeList", "https://myanimelist.net/anime/season", "")
        return {"anime": daftar, "nomor": nomor}


def ringkas_anime(item, jenis, singkat=False):
    hasil = {
        "judul": item.get("title"), "judul_inggris": item.get("title_english"), "url": item.get("url", ""),
        "tipe": item.get("type"), "status": item.get("status"), "skor": item.get("score"),
        "genre": [g.get("name") for g in item.get("genres") or []],
    }
    if jenis == "anime":
        hasil.update({"episode": item.get("episodes"), "tayang": (item.get("aired") or {}).get("string"),
                      "studio": [s.get("name") for s in item.get("studios") or []], "musim": f"{item.get('season') or ''} {item.get('year') or ''}".strip()})
    else:
        hasil.update({"chapter": item.get("chapters"), "volume": item.get("volumes"), "terbit": (item.get("published") or {}).get("string"),
                      "pengarang": [a.get("name") for a in item.get("authors") or []]})
    if not singkat:
        hasil.update({"peringkat": item.get("rank"), "sinopsis": (item.get("synopsis") or "")[:800]})
    return hasil