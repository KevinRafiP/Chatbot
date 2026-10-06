import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote, urlparse


def tanda_tangani(metode, alamat, badan, wilayah, layanan, access_key, secret_key, header=None, waktu=None):
    """Membuat header bertanda tangan AWS Signature Version 4 untuk satu request."""
    waktu = waktu or datetime.now(timezone.utc)
    cap_waktu = waktu.strftime("%Y%m%dT%H%M%SZ")
    tanggal = waktu.strftime("%Y%m%d")
    bagian = urlparse(alamat)

    header = {k.lower(): v.strip() for k, v in (header or {}).items()}
    header["host"] = bagian.netloc
    header["x-amz-date"] = cap_waktu
    nama_header = ";".join(sorted(header))

    permintaan_baku = "\n".join([
        metode,
        quote(bagian.path or "/", safe="/"),
        bagian.query,
        "".join(f"{k}:{header[k]}\n" for k in sorted(header)),
        nama_header,
        hashlib.sha256(badan).hexdigest(),
    ])

    lingkup = f"{tanggal}/{wilayah}/{layanan}/aws4_request"
    teks_ditandatangani = "\n".join([
        "AWS4-HMAC-SHA256",
        cap_waktu,
        lingkup,
        hashlib.sha256(permintaan_baku.encode("utf-8")).hexdigest(),
    ])

    kunci = ("AWS4" + secret_key).encode("utf-8")
    for potongan in (tanggal, wilayah, layanan, "aws4_request"):
        kunci = hmac.new(kunci, potongan.encode("utf-8"), hashlib.sha256).digest()
    tanda = hmac.new(kunci, teks_ditandatangani.encode("utf-8"), hashlib.sha256).hexdigest()

    header["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{lingkup}, SignedHeaders={nama_header}, Signature={tanda}"
    )
    del header["host"]
    return header