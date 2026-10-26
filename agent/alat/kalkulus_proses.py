"""Dijalankan sebagai proses terpisah oleh alat/kalkulus.py: membaca JSON dari stdin dan menulis hasilnya ke stdout.
Proses terpisah dipakai agar soal yang terlalu berat bisa dihentikan dengan batas waktu tanpa membuat agent macet."""
import json
import re
import sys

BATAS_PANJANG = 300
# hanya nama-nama ini yang boleh muncul, agar teks tidak bisa menjalankan kode Python lain
NAMA_DIIZINKAN = {
    "x", "y", "z", "t", "n", "k", "a", "b", "c", "u", "v", "w", "r", "theta",
    "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "exp", "log", "ln", "sqrt", "abs", "pi", "e", "E", "oo", "inf", "factorial",
}
POLA_KARAKTER = re.compile(r"^[0-9A-Za-z+\-*/^()., =<>!]*$")
POLA_NAMA = re.compile(r"[A-Za-z]+")


def periksa(teks):
    teks = str(teks or "").strip()
    if not teks or len(teks) > BATAS_PANJANG:
        raise ValueError("ekspresi kosong atau terlalu panjang")
    if not POLA_KARAKTER.match(teks) or re.search(r"[A-Za-z_]\.|\.[A-Za-z_]", teks):
        raise ValueError("ekspresi berisi karakter yang tidak diizinkan")
    asing = {nama for nama in POLA_NAMA.findall(teks) if nama not in NAMA_DIIZINKAN}
    if asing:
        raise ValueError(f"nama tidak dikenal: {', '.join(sorted(asing))}; pakai variabel x, y, z, t, n atau fungsi matematika umum")
    return teks


def main():
    import sympy
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application, parse_expr,
                                            standard_transformations)

    transformasi = standard_transformations + (implicit_multiplication_application, convert_xor)
    nama = {s: sympy.Symbol(s) for s in ("x", "y", "z", "t", "n", "k", "a", "b", "c", "u", "v", "w", "r", "theta")}
    nama.update({"ln": sympy.log, "e": sympy.E, "E": sympy.E, "inf": sympy.oo, "oo": sympy.oo, "pi": sympy.pi})

    def baca(teks):
        return parse_expr(periksa(teks), local_dict=nama, transformations=transformasi, evaluate=True)

    data = json.loads(sys.stdin.read())
    operasi = str(data.get("operasi", "sederhanakan")).lower()
    variabel = nama.get(str(data.get("variabel") or "x"), nama["x"])

    if operasi == "selesaikan":
        persamaan = str(data.get("ekspresi", ""))
        if "=" in persamaan:
            kiri, _, kanan = persamaan.partition("=")
            ekspresi = sympy.Eq(baca(kiri), baca(kanan))
        else:
            ekspresi = sympy.Eq(baca(persamaan), 0)
        hasil = sympy.solve(ekspresi, variabel)
        keluaran = {"solusi": [str(h) for h in hasil], "solusi_latex": [sympy.latex(h) for h in hasil],
                    "solusi_desimal": [str(sympy.N(h, 8)) for h in hasil]}
    else:
        ekspresi = baca(data.get("ekspresi"))
        if operasi == "turunan":
            orde = min(max(int(data.get("orde") or 1), 1), 10)
            hasil = sympy.diff(ekspresi, variabel, orde)
        elif operasi == "integral":
            bawah, atas = data.get("batas_bawah"), data.get("batas_atas")
            if bawah not in (None, "") and atas not in (None, ""):
                hasil = sympy.integrate(ekspresi, (variabel, baca(str(bawah)), baca(str(atas))))
            else:
                hasil = sympy.integrate(ekspresi, variabel)
        elif operasi == "limit":
            arah = {"kiri": "-", "kanan": "+"}.get(str(data.get("arah", "")).lower(), "+-")
            hasil = sympy.limit(ekspresi, variabel, baca(str(data.get("menuju", "0"))), arah)
        elif operasi == "faktorkan":
            hasil = sympy.factor(ekspresi)
        elif operasi == "jabarkan":
            hasil = sympy.expand(ekspresi)
        elif operasi == "sederhanakan":
            hasil = sympy.simplify(ekspresi)
        else:
            raise ValueError("operasi harus turunan, integral, limit, selesaikan, faktorkan, jabarkan, atau sederhanakan")
        keluaran = {"hasil": str(hasil), "hasil_latex": sympy.latex(hasil)}
        if hasil.is_number:
            keluaran["hasil_desimal"] = str(sympy.N(hasil, 10))
        if operasi == "integral" and data.get("batas_bawah") in (None, ""):
            keluaran["catatan"] = "Integral tak tentu: tambahkan konstanta C."
    keluaran["masukan_latex"] = sympy.latex(ekspresi)
    print(json.dumps(keluaran, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as galat:
        print(json.dumps({"galat": str(galat)[:300]}, ensure_ascii=False))