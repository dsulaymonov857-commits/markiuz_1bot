import unittest
from zipfile import ZipFile
from io import BytesIO

from app.handlers import create_zip_with_pdf


class HandlerZipTest(unittest.TestCase):
    def test_create_zip_with_pdf(self) -> None:
        pdf = b"%PDF-test"
        archive_data = create_zip_with_pdf(pdf, "codes.pdf")

        with ZipFile(BytesIO(archive_data)) as archive:
            self.assertEqual(archive.namelist(), ["codes.pdf"])
            self.assertEqual(archive.read("codes.pdf"), pdf)


if __name__ == "__main__":
    unittest.main()
