import ast
import math
import operator

BATAS_PANJANG = 300
BATAS_PANGKAT = 1000

OPERATOR = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
FUNGSI = {
    "sqrt": math.sqrt, "akar": math.sqrt, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
    "log": math.log10, "ln": math.log, "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "radians": math.radians, "degrees": math.degrees, "factorial": math.factorial, "min": min, "max": max,
}
KONSTANTA = {"pi": math.pi, "e": math.e}


def hitung(ekspresi):
    """Menghitung ekspresi matematika tanpa eval: angka, + - * / // % ** ^, kurung, fungsi di FUNGSI, serta pi dan e."""
    teks = str(ekspresi).strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    if not teks or len(teks) > BATAS_PANJANG:
        raise ValueError("ekspresi kosong atau terlalu panjang")
    try:
        pohon = ast.parse(teks, mode="eval")
    except SyntaxError:
        raise ValueError("ekspresi tidak bisa dibaca")
    nilai = nilai_simpul(pohon.body)
    if isinstance(nilai, float):
        nilai = round(nilai, 10)
        if nilai.is_integer() and abs(nilai) < 1e15:
            nilai = int(nilai)
    return nilai


def nilai_simpul(simpul):
    if isinstance(simpul, ast.Constant) and type(simpul.value) in (int, float):
        return simpul.value
    if isinstance(simpul, ast.Name) and simpul.id in KONSTANTA:
        return KONSTANTA[simpul.id]
    if isinstance(simpul, ast.UnaryOp) and type(simpul.op) in OPERATOR:
        return OPERATOR[type(simpul.op)](nilai_simpul(simpul.operand))
    if isinstance(simpul, ast.BinOp) and type(simpul.op) in OPERATOR:
        kiri, kanan = nilai_simpul(simpul.left), nilai_simpul(simpul.right)
        # pangkat besar bisa membuat server macet, jadi dibatasi
        if isinstance(simpul.op, ast.Pow) and (abs(kanan) > BATAS_PANGKAT or abs(kiri) > 10 ** 6 and abs(kanan) > 50):
            raise ValueError("pangkat terlalu besar")
        return OPERATOR[type(simpul.op)](kiri, kanan)
    if isinstance(simpul, ast.Call) and isinstance(simpul.func, ast.Name) and simpul.func.id in FUNGSI and not simpul.keywords:
        argumen = [nilai_simpul(a) for a in simpul.args]
        if simpul.func.id == "factorial" and (argumen and argumen[0] > BATAS_PANGKAT):
            raise ValueError("faktorial terlalu besar")
        return FUNGSI[simpul.func.id](*argumen)
    raise ValueError("ekspresi hanya boleh berisi angka, operator, kurung, dan fungsi matematika dasar")