import importlib.util
import io
import re
import zipfile
from html import unescape

from alat.jaringan import GalatAlat

MAKS_HALAMAN_PDF = 60
MAKS_XML_DOCX = 20_000_000
JENIS_TEKS = (".txt", ".md", ".csv", ".json", ".log", ".html", ".htm", ".xml", ".py", ".go", ".js", ".ts", ".sql")
POLA_TAG = re.compile(r"<[^>]+>")


def pdf_didukung():
    return importlib.util.find_spec("pypdf") is not None


def jenis_didukung():
    daftar = list(JENIS_TEKS) + [".docx"]
    if pdf_didukung():
        daftar.append(".pdf")
    return daftar


def baca_berkas(nama, isi, maks_huruf):
    """Mengambil teks dari berkas unggahan: PDF (perlu pypdf), DOCX, dan berkas teks biasa."""
    nama = str(nama or "berkas").strip()[:200]
    akhiran = "." + nama.rsplit(".", 1)[-1].lower() if "." in nama else ""
    if akhiran == ".pdf":
        teks, halaman = baca_pdf(isi)
    elif akhiran == ".docx":
        teks, halaman = baca_docx(isi), None
    elif akhiran in JENIS_TEKS:
        teks, halaman = baca_teks(isi), None
        if akhiran in (".html", ".htm", ".xml"):
            teks = unescape(POLA_TAG.sub(" ", teks))
    else:
        raise GalatAlat(f"jenis berkas belum didukung; yang didukung: {', '.join(jenis_didukung())}")

    teks = re.sub(r"[ \t]+", " ", teks)
    teks = re.sub(r"\n\s*\n\s*\n+", "\n\n", teks).strip()
    if not teks:
        raise GalatAlat("berkas tidak berisi teks (mungkin hasil scan gambar)")
    terpotong = len(teks) > maks_huruf
    return {"nama": nama, "teks": teks[:maks_huruf], "jumlah_huruf": len(teks), "terpotong": terpotong, "halaman": halaman}


def baca_teks(isi):
    for pengkodean in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return isi.decode(pengkodean)
        except UnicodeDecodeError:
            continue
    return isi.decode("utf-8", errors="replace")


def baca_pdf(isi):
    if not pdf_didukung():
        raise GalatAlat("membaca PDF belum aktif di server (paket pypdf belum dipasang)")
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        pembaca = PdfReader(io.BytesIO(isi))
        if pembaca.is_encrypted:
            raise GalatAlat("PDF dikunci kata sandi")
        halaman = pembaca.pages[:MAKS_HALAMAN_PDF]
        return "\n\n".join((h.extract_text() or "") for h in halaman), len(pembaca.pages)
    except (PdfReadError, ValueError, KeyError) as galat:
        raise GalatAlat(f"PDF tidak bisa dibaca: {str(galat)[:100]}")


def baca_docx(isi):
    try:
        with zipfile.ZipFile(io.BytesIO(isi)) as arsip:
            info = arsip.getinfo("word/document.xml")
            # file zip bisa berisi data yang membesar ribuan kali saat dibuka, jadi ukurannya diperiksa dulu
            if info.file_size > MAKS_XML_DOCX:
                raise GalatAlat("isi dokumen terlalu besar")
            xml = arsip.read(info).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError):
        raise GalatAlat("berkas DOCX rusak atau bukan dokumen Word")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return unescape(POLA_TAG.sub("", xml))