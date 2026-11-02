"""Dijalankan sebagai proses terpisah oleh alat/kalkulus.py: membaca JSON dari stdin dan menulis hasilnya ke stdout.
Proses terpisah dipakai agar soal yang terlalu berat bisa dihentikan dengan batas waktu tanpa membuat agent macet."""
import json
import re
import sys

BATAS_PANJANG = 600
VARIABEL = ("x", "y", "z", "t", "n", "k", "a", "b", "c", "m", "p", "q", "s", "u", "v", "w", "r",
            "theta", "alpha", "beta", "mu", "sigma", "phi", "omega")
# hanya nama-nama ini yang boleh muncul, agar teks tidak bisa menjalankan kode Python lain
NAMA_DIIZINKAN = set(VARIABEL) | {
    "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan", "sinh", "cosh", "tanh",
    "exp", "log", "ln", "sqrt", "abs", "pi", "e", "E", "oo", "inf", "factorial", "binomial", "I",
}
POLA_KARAKTER = re.compile(r"^[0-9A-Za-z+\-*/^()., =<>!\[\];']*$")
POLA_NAMA = re.compile(r"[A-Za-z]+")
# y, y', y'', y''' pada persamaan diferensial diganti nama sementara sebelum dibaca SymPy
POLA_TURUNAN_Y = re.compile(r"(?:^|(?<=[^A-Za-z]))y('{0,3})")
OPERASI_MATRIKS = ("determinan", "invers", "eigen", "rref", "transpos", "rank")
OPERASI = ("turunan", "integral", "limit", "selesaikan", "faktorkan", "jabarkan", "sederhanakan", "deret", "taylor",
           "diferensial") + OPERASI_MATRIKS


def periksa(teks, petik=False):
    teks = str(teks or "").strip()
    if not teks or len(teks) > BATAS_PANJANG:
        raise ValueError("ekspresi kosong atau terlalu panjang")
    if not POLA_KARAKTER.match(teks) or re.search(r"[A-Za-z_]\.|\.[A-Za-z_]", teks) or ("'" in teks and not petik):
        raise ValueError("ekspresi berisi karakter yang tidak diizinkan")
    asing = {nama for nama in POLA_NAMA.findall(teks) if nama not in NAMA_DIIZINKAN}
    if asing:
        raise ValueError(f"nama tidak dikenal: {', '.join(sorted(asing))}; pakai variabel seperti x, y, z, t, n atau fungsi matematika umum")
    return teks


def main():
    import sympy
    from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication_application, parse_expr,
                                            standard_transformations)

    transformasi = standard_transformations + (implicit_multiplication_application, convert_xor)
    nama = {s: sympy.Symbol(s) for s in VARIABEL}
    nama.update({"ln": sympy.log, "e": sympy.E, "E": sympy.E, "inf": sympy.oo, "oo": sympy.oo, "pi": sympy.pi, "I": sympy.I})

    def baca(teks, tambahan=None):
        return parse_expr(teks if tambahan else periksa(teks), local_dict={**nama, **(tambahan or {})},
                          transformations=transformasi, evaluate=True)

    def persamaan(teks, tambahan=None):
        kiri, sama, kanan = teks.partition("=")
        return sympy.Eq(baca(kiri, tambahan), baca(kanan, tambahan)) if sama else sympy.Eq(baca(teks, tambahan), 0)

    def ke_variabel(teks, bawaan="x"):
        daftar = [nama[v.strip()] for v in str(teks or bawaan).split(",") if v.strip() in nama]
        return daftar or [nama[bawaan]]

    data = json.loads(sys.stdin.read())
    operasi = str(data.get("operasi", "sederhanakan")).lower()
    if operasi not in OPERASI:
        raise ValueError(f"operasi harus salah satu dari: {', '.join(OPERASI)}")
    daftar_variabel = ke_variabel(data.get("variabel"))
    variabel = daftar_variabel[0]
    teks = str(data.get("ekspresi", ""))
    keluaran = {}

    if operasi == "selesaikan":
        # beberapa persamaan dipisah titik koma menjadi sistem persamaan, contoh "x + y = 3; x - y = 1" dengan variabel "x,y"
        semua = [persamaan(periksa(bagian)) for bagian in teks.split(";") if bagian.strip()]
        hasil = sympy.solve(semua if len(semua) > 1 else semua[0], daftar_variabel if len(semua) > 1 else variabel, dict=len(semua) > 1)
        keluaran = {"solusi": [str(h) for h in hasil], "solusi_latex": [latex_solusi(sympy, h) for h in hasil]}
        if all(not isinstance(h, dict) and h.is_number for h in hasil):
            keluaran["solusi_desimal"] = [str(sympy.N(h, 8)) for h in hasil]
        ekspresi = semua[0] if len(semua) == 1 else semua
    elif operasi == "diferensial":
        ekspresi, hasil = diferensial(sympy, periksa(teks, petik=True), variabel, data.get("kondisi"), persamaan)
        keluaran = {"hasil": str(hasil), "hasil_latex": sympy.latex(hasil)}
    elif operasi in OPERASI_MATRIKS:
        ekspresi = sympy.Matrix(baca(teks))
        keluaran = matriks(sympy, operasi, ekspresi)
    else:
        ekspresi = baca(teks)
        if operasi == "turunan":
            # turunan parsial: variabel diisi y atau "x,y" untuk turunan campuran
            orde = min(max(int(data.get("orde") or 1), 1), 10)
            hasil = sympy.diff(ekspresi, *daftar_variabel) if len(daftar_variabel) > 1 else sympy.diff(ekspresi, variabel, orde)
        elif operasi == "integral":
            bawah, atas = data.get("batas_bawah"), data.get("batas_atas")
            if bawah not in (None, "") and atas not in (None, ""):
                hasil = sympy.integrate(ekspresi, (variabel, baca(str(bawah)), baca(str(atas))))
            else:
                hasil = sympy.integrate(ekspresi, variabel)
                keluaran["catatan"] = "Integral tak tentu: tambahkan konstanta C."
        elif operasi == "limit":
            arah = {"kiri": "-", "kanan": "+"}.get(str(data.get("arah", "")).lower(), "+-")
            hasil = sympy.limit(ekspresi, variabel, baca(str(data.get("menuju", "0"))), arah)
        elif operasi == "deret":
            hasil = sympy.summation(ekspresi, (variabel, baca(str(data.get("batas_bawah") or "1")), baca(str(data.get("batas_atas") or "oo"))))
        elif operasi == "taylor":
            orde = min(max(int(data.get("orde") or 5), 1), 20)
            hasil = sympy.series(ekspresi, variabel, baca(str(data.get("menuju") or "0")), orde + 1).removeO()
        elif operasi == "faktorkan":
            hasil = sympy.factor(ekspresi)
        elif operasi == "jabarkan":
            hasil = sympy.expand(ekspresi)
        else:
            hasil = sympy.simplify(ekspresi)
        keluaran.update({"hasil": str(hasil), "hasil_latex": sympy.latex(hasil)})
        if hasil.is_number:
            keluaran["hasil_desimal"] = str(sympy.N(hasil, 10))
    keluaran["masukan_latex"] = sympy.latex(ekspresi)
    print(json.dumps(keluaran, ensure_ascii=False))


def latex_solusi(sympy, solusi):
    if isinstance(solusi, dict):
        return ", ".join(f"{sympy.latex(k)} = {sympy.latex(v)}" for k, v in solusi.items())
    return sympy.latex(solusi)


def diferensial(sympy, teks, variabel, kondisi, persamaan):
    """Persamaan diferensial biasa dengan y sebagai fungsi variabel, contoh "y'' + 3y' + 2y = 0" dan kondisi "y(0)=1; y'(0)=0"."""
    y = sympy.Function("y")(variabel)
    turunan = {f"Y{orde}": y.diff(variabel, orde) if orde else y for orde in range(4)}
    ganti = lambda teks_ini: POLA_TURUNAN_Y.sub(lambda c: f"Y{len(c.group(1))}", teks_ini)
    ekspresi = persamaan(ganti(teks), turunan)

    ics = {}
    for bagian in str(kondisi or "").split(";"):
        cocok = re.fullmatch(r"\s*y('{0,3})\(([^()]+)\)\s*=\s*(.+)", bagian)
        if not cocok:
            continue
        titik = sympy.sympify(periksa(cocok.group(2)), locals={})
        nilai = sympy.sympify(periksa(cocok.group(3)), locals={})
        orde = len(cocok.group(1))
        kunci = y.diff(variabel, orde).subs(variabel, titik) if orde else y.subs(variabel, titik)
        ics[kunci] = nilai
    return ekspresi, sympy.dsolve(ekspresi, y, ics=ics or None)


def matriks(sympy, operasi, m):
    if operasi == "determinan":
        hasil = m.det()
    elif operasi == "invers":
        hasil = m.inv()
    elif operasi == "transpos":
        hasil = m.T
    elif operasi == "rank":
        hasil = sympy.Integer(m.rank())
    elif operasi == "rref":
        hasil = m.rref()[0]
    else:
        nilai = m.eigenvects()
        return {"nilai_eigen": [{"nilai": str(v), "nilai_latex": sympy.latex(v), "kelipatan": k,
                                 "vektor_latex": [sympy.latex(vektor) for vektor in daftar]} for v, k, daftar in nilai]}
    return {"hasil": str(hasil), "hasil_latex": sympy.latex(hasil)}


if __name__ == "__main__":
    try:
        main()
    except Exception as galat:
        print(json.dumps({"galat": str(galat)[:300]}, ensure_ascii=False))
