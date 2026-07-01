import unittest

import fitz
import zxingcpp
from PIL import Image

from app.code_files import read_codes
from app.datamatrix_pdf import create_datamatrix_pdf


class DataMatrixPdfTest(unittest.TestCase):
    def test_csv_codes_are_rendered_as_readable_datamatrix(self) -> None:
        raw_code = (
            "0106921817810016217?_)A=w<D/3Lzp;,:A%L"
            "<GS>91liO1<GS>92+XVESGI5bEtjSDI5ODJ2V1pYPUlIKnJHajl6c4kdsXs="
        )
        codes = read_codes("codes.csv", f'code\n"{raw_code}"'.encode())
        pdf = create_datamatrix_pdf(codes)
        document = fitz.open(stream=pdf, filetype="pdf")
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        decoded = zxingcpp.read_barcodes(image)
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0].content_type, zxingcpp.ContentType.GS1)
        self.assertEqual(decoded[0].symbology_identifier, "]d2")
        self.assertEqual(
            bytes(decoded[0].bytes),
            raw_code.replace("<GS>", "\x1d").encode(),
        )

    def test_rejects_plain_gtin(self) -> None:
        with self.assertRaisesRegex(ValueError, "To'liq Asl Belgisi"):
            create_datamatrix_pdf(["4780172600012"])

    def test_recovers_separators_removed_by_xlsx(self) -> None:
        expected_code = (
            "0106921817810016217?_)A=w<D/3Lzp;,:A%L"
            "\x1d91liO1\x1d92+XVESGI5bEtjSDI5ODJ2V1pYPUlIKnJHajl6c4kdsXs="
        )
        xlsx_code = expected_code.replace("\x1d", "")
        codes = read_codes("codes.xlsx", _xlsx_with_code(xlsx_code))
        self.assertEqual(codes, [xlsx_code])

        pdf = create_datamatrix_pdf(codes)
        document = fitz.open(stream=pdf, filetype="pdf")
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        decoded = zxingcpp.read_barcodes(image)

        self.assertEqual(len(decoded), 1)
        self.assertEqual(bytes(decoded[0].bytes), expected_code.encode())

    def test_csv_commas_inside_unquoted_code_are_preserved(self) -> None:
        raw_code = (
            "0106921817810016217?_)A=w<D/3Lzp;,:A%L"
            "91liO192+XVESGI5bEtjSDI5ODJ2V1pYPUlIKnJHajl6c4kdsXs="
        )
        codes = read_codes("codes.csv", f"code\n{raw_code}".encode())
        self.assertEqual(codes, [raw_code])
        self.assertTrue(create_datamatrix_pdf(codes).startswith(b"%PDF"))

    def test_csv_real_ascii_29_does_not_split_code(self) -> None:
        raw_code = (
            "0106921817810016217?_)A=w<D/3Lzp;,:A%L"
            "\x1d91liO1\x1d92+XVESGI5bEtjSDI5ODJ2V1pYPUlIKnJHajl6c4kdsXs="
        )
        codes = read_codes("codes.csv", raw_code.encode())
        self.assertEqual(codes, [raw_code])
        self.assertTrue(create_datamatrix_pdf(codes).startswith(b"%PDF"))


def _xlsx_with_code(code: str) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active["A1"] = code
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
