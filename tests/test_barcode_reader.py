import unittest

import fitz

from app.barcode_reader import read_gtins_from_pdf


class BarcodeReaderTest(unittest.TestCase):
    def test_reads_unique_gtins_from_pdf_text(self) -> None:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "GTIN: 4780123456789")
        page.insert_text((72, 100), "Duplicate: 4780123456789")
        page.insert_text((72, 128), "Second: 12345678")
        pdf_bytes = document.tobytes()
        document.close()

        self.assertEqual(
            read_gtins_from_pdf(pdf_bytes),
            ["12345678", "4780123456789"],
        )


if __name__ == "__main__":
    unittest.main()
