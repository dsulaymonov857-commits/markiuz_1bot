from io import BytesIO
import re

import zxingcpp
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


def _escape_ai_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def normalize_gs1_marking_code(raw_code: str) -> str:
    code = (
        raw_code.strip(" \t\r\n")
        .lstrip("'")
        .replace("\u200b", "")
        .replace("\\u001D", "\x1d")
        .replace("\\u001d", "\x1d")
        .replace("<GS>", "\x1d")
        .replace("<gs>", "\x1d")
    )
    if code.startswith("]d2"):
        code = code[3:]
    if code.startswith("(01)") and "(21)" in code and "(91)" in code and "(92)" in code:
        return code
    if code.startswith("(01)") and "(21)" in code and "(93)" in code:
        return code

    match = re.fullmatch(
        r"01(\d{14})21(.+?)\x1d91(.+?)\x1d92(.+)",
        code,
        flags=re.DOTALL,
    )
    if not match:
        # XLSX cannot store ASCII 29. Recover the standard structure where
        # AI 91 contains the four-character crypto key identifier.
        match = re.fullmatch(
            r"01(\d{14})21(.+)91(.{4})92(.+)",
            code,
            flags=re.DOTALL,
        )
    if not match:
        mineral_match = re.fullmatch(
            r"01(\d{14})21(.+?)\x1d93(.+)",
            code,
            flags=re.DOTALL,
        )
        if mineral_match:
            gtin, serial, verification = mineral_match.groups()
            return (
                f"(01){gtin}"
                f"(21){_escape_ai_value(serial)}"
                f"(93){_escape_ai_value(verification)}"
            )
        raise ValueError(
            "To'liq Asl Belgisi markirovka kodi kerak: 01+GTIN, 21+serial, "
            "91/92 yoki 93 qismi bo'lishi shart."
        )
    gtin, serial, crypto_key, crypto_signature = match.groups()
    return (
        f"(01){gtin}"
        f"(21){_escape_ai_value(serial)}"
        f"(91){_escape_ai_value(crypto_key)}"
        f"(92){_escape_ai_value(crypto_signature)}"
    )


def create_datamatrix_pdf(codes: list[str], product_type: str | None = None) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    _, page_height = A4
    columns, rows = 7, 10
    matrix_size = 56
    margin_x, margin_y = 12, 12
    gap_x, gap_y = 29, 24
    per_page = columns * rows

    for index, raw_code in enumerate(codes):
        if index and index % per_page == 0:
            canvas.showPage()

        position = index % per_page
        column = position % columns
        row = position // columns
        x = margin_x + column * (matrix_size + gap_x)
        top_y = margin_y + row * (matrix_size + gap_y)
        y = page_height - top_y - matrix_size

        try:
            code = normalize_gs1_marking_code(raw_code)
        except ValueError as exc:
            preview = raw_code.replace("\x1d", "<GS>")
            if len(preview) > 90:
                preview = f"{preview[:87]}..."
            raise ValueError(f"{index + 1}-qator noto'g'ri: {preview}\n{exc}") from exc
        barcode = zxingcpp.create_barcode(
            code,
            zxingcpp.BarcodeFormat.DataMatrix,
            gs1=True,
            force_square=True,
        )
        matrix = Image.fromarray(
            zxingcpp.write_barcode_to_image(barcode, scale=10, add_quiet_zones=True)
        )
        matrix_buffer = BytesIO()
        matrix.save(matrix_buffer, format="PNG")
        matrix_buffer.seek(0)
        canvas.drawImage(
            ImageReader(matrix_buffer),
            x,
            y,
            width=matrix_size,
            height=matrix_size,
            preserveAspectRatio=True,
            mask="auto",
        )

    if product_type:
        canvas.setTitle(f"{product_type} DataMatrix")
    canvas.save()
    return output.getvalue()
