from io import BytesIO
import re
import textwrap

import zxingcpp
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
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
    page_width, page_height = A4
    columns, rows = 2, 3
    cell_width = page_width / columns
    cell_height = page_height / rows
    matrix_size = 145

    for index, raw_code in enumerate(codes):
        if index and index % (columns * rows) == 0:
            canvas.showPage()

        position = index % (columns * rows)
        column = position % columns
        row = position // columns
        x = column * cell_width
        y = page_height - (row + 1) * cell_height

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
        matrix = Image.fromarray(zxingcpp.write_barcode_to_image(barcode, matrix_size))
        matrix_buffer = BytesIO()
        matrix.save(matrix_buffer, format="PNG")
        matrix_buffer.seek(0)
        canvas.drawImage(
            ImageReader(matrix_buffer),
            x + (cell_width - matrix_size) / 2,
            y + 92,
            width=matrix_size,
            height=matrix_size,
            preserveAspectRatio=True,
            mask="auto",
        )

        label_source = raw_code.replace("\x1d", "<GS>")
        label_lines = textwrap.wrap(
            label_source,
            width=42,
            break_long_words=True,
            break_on_hyphens=False,
        )
        canvas.setFont("Courier", 6)
        for line_index, label in enumerate(label_lines[:5]):
            label_width = stringWidth(label, "Courier", 6)
            canvas.drawString(
                x + (cell_width - label_width) / 2,
                y + 72 - line_index * 8,
                label,
            )

    canvas.save()
    return output.getvalue()
