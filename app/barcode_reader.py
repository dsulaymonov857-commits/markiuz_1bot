import re
from io import BytesIO

import fitz
import zxingcpp
from PIL import Image


GTIN_PATTERN = re.compile(r"(?<!\d)(\d{8}|\d{12}|\d{13}|\d{14})(?!\d)")


def _normalize_gtin(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) in {8, 12, 13, 14} else None


def read_gtins_from_pdf(pdf_bytes: bytes) -> list[str]:
    found: set[str] = set()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        for page in document:
            found.update(GTIN_PATTERN.findall(page.get_text()))

            pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            for barcode in zxingcpp.read_barcodes(image):
                gtin = _normalize_gtin(barcode.text)
                if gtin:
                    found.add(gtin)

    return sorted(found)
