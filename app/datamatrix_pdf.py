from io import BytesIO
import re
import textwrap
import zipfile

import zxingcpp
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


def normalize_marking_code_components(raw_code: str) -> tuple[str, str]:
    code = (
        raw_code.strip(" \t\r\n")
        .lstrip("'")
        .replace("\u200b", "")
        .replace("_x001D_", "\x1d")
        .replace("_x001d_", "\x1d")
        .replace("\\u001D", "\x1d")
        .replace("\\u001d", "\x1d")
        .replace("<GS>", "\x1d")
        .replace("<gs>", "\x1d")
        .replace("[GS]", "\x1d")
        .replace("[gs]", "\x1d")
    )
    if code.startswith("]d2"):
        code = code[3:]

    gtin = None
    serial = None
    ai91 = None
    ai92 = None
    ai93 = None

    if code.startswith("(01)"):
        m_full_91 = re.fullmatch(
            r"\(01\)(\d{14})\(21\)(.+?)\(91\)(.+?)\(92\)(.+)", code, flags=re.DOTALL
        )
        m_full_93 = re.fullmatch(
            r"\(01\)(\d{14})\(21\)(.+?)\(93\)(.+)", code, flags=re.DOTALL
        )
        if m_full_91:
            gtin, serial, ai91, ai92 = m_full_91.groups()
        elif m_full_93:
            gtin, serial, ai93 = m_full_93.groups()
        else:
            m_part = re.fullmatch(
                r"\(01\)(\d{14})\(21\)(.+?)\x1d93(.+)", code, flags=re.DOTALL
            )
            if m_part:
                gtin, serial, ai93 = m_part.groups()
            else:
                m_part2 = re.fullmatch(
                    r"\(01\)(\d{14})\(21\)(.+?)\x1d91(.+?)\x1d92(.+)",
                    code,
                    flags=re.DOTALL,
                )
                if m_part2:
                    gtin, serial, ai91, ai92 = m_part2.groups()

    if not gtin:
        # 1. Standard with 91 and 92 (with separator)
        m = re.fullmatch(
            r"01(\d{14})21(.+?)\x1d91(.+?)\x1d92(.+)",
            code,
            flags=re.DOTALL,
        )
        if m:
            gtin, serial, ai91, ai92 = m.groups()
        # 2. Short crypto with 93 (with separator, e.g. fertilizers/water)
        if not gtin:
            m = re.fullmatch(
                r"01(\d{14})21(.+?)\x1d93(.+)",
                code,
                flags=re.DOTALL,
            )
            if m:
                gtin, serial, ai93 = m.groups()
        # 3. Standard with 91 and 92 (without separator - XLSX)
        if not gtin:
            m = re.fullmatch(
                r"01(\d{14})21(.+)91(.{4})92(.+)",
                code,
                flags=re.DOTALL,
            )
            if m:
                gtin, serial, ai91, ai92 = m.groups()
        # 4. Short crypto with 93 (without separator - XLSX)
        if not gtin:
            m = re.fullmatch(
                r"01(\d{14})21(.+)93(.{4})$",
                code,
                flags=re.DOTALL,
            )
            if m:
                gtin, serial, ai93 = m.groups()

    if not gtin:
        raise ValueError(
            "To'liq Asl Belgisi markirovka kodi kerak: 01+GTIN, 21+serial "
            "va 91/92 yoki 93 kriptografik qismlari bo'lishi shart."
        )

    esc_serial = serial.replace("(", "\\(")
    if ai93 is not None:
        esc_ai93 = ai93.replace("(", "\\(")
        hri = f"(01){gtin}(21){esc_serial}(93){esc_ai93}"
        raw_gs = f"01{gtin}21{serial}\x1d93{ai93}"
    else:
        esc_ai91 = ai91.replace("(", "\\(")
        esc_ai92 = ai92.replace("(", "\\(")
        hri = f"(01){gtin}(21){esc_serial}(91){esc_ai91}(92){esc_ai92}"
        raw_gs = f"01{gtin}21{serial}\x1d91{ai91}\x1d92{ai92}"

    return hri, raw_gs


normalize_gs1_marking_code = normalize_marking_code_components


def create_datamatrix_pdf(codes: list[str]) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    page_width, page_height = A4
    columns = 7
    rows = 10
    per_page = columns * rows  # 70 codes per A4 page

    margin_x = 18
    margin_y = 25
    usable_w = page_width - margin_x * 2
    usable_h = page_height - margin_y * 2
    cell_width = usable_w / columns
    cell_height = usable_h / rows
    matrix_size = 58

    for index, raw_code in enumerate(codes):
        if index and index % per_page == 0:
            canvas.showPage()

        pos = index % per_page
        col = pos % columns
        row = pos // columns

        x = margin_x + col * cell_width + (cell_width - matrix_size) / 2
        y = (
            page_height
            - margin_y
            - (row + 1) * cell_height
            + (cell_height - matrix_size) / 2
        )

        try:
            hri_code, raw_gs_code = normalize_marking_code_components(raw_code)
        except ValueError as exc:
            preview = raw_code.replace("\x1d", "<GS>")
            if len(preview) > 90:
                preview = f"{preview[:87]}..."
            raise ValueError(f"{index + 1}-qator noto'g'ri: {preview}\n{exc}") from exc

        try:
            barcode = zxingcpp.create_barcode(
                hri_code,
                zxingcpp.BarcodeFormat.DataMatrix,
                gs1=True,
                force_square=True,
            )
        except Exception:
            barcode = zxingcpp.create_barcode(
                raw_gs_code,
                zxingcpp.BarcodeFormat.DataMatrix,
                force_square=True,
            )

        scale = 5
        matrix = Image.fromarray(zxingcpp.write_barcode_to_image(barcode, scale))
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

    canvas.save()
    return output.getvalue()


def create_datamatrix_zip(codes: list[str]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        scale = 15  # 24 modules * 15 = 360px crisp square DataMatrix image
        for index, raw_code in enumerate(codes, start=1):
            try:
                hri_code, raw_gs_code = normalize_marking_code_components(raw_code)
            except ValueError:
                continue

            try:
                barcode = zxingcpp.create_barcode(
                    hri_code,
                    zxingcpp.BarcodeFormat.DataMatrix,
                    gs1=True,
                    force_square=True,
                )
            except Exception:
                barcode = zxingcpp.create_barcode(
                    raw_gs_code,
                    zxingcpp.BarcodeFormat.DataMatrix,
                    force_square=True,
                )

            matrix_img = Image.fromarray(
                zxingcpp.write_barcode_to_image(barcode, scale)
            )
            png_buffer = BytesIO()
            matrix_img.save(png_buffer, format="PNG")
            zf.writestr(f"{index:04d}_datamatrix.png", png_buffer.getvalue())

    return output.getvalue()


