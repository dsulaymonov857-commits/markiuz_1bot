import unittest

from app.code_files import (
    read_codes,
    select_full_marking_codes,
)
from app.datamatrix_pdf import create_datamatrix_pdf, normalize_gs1_marking_code


class CodeFilesTest(unittest.TestCase):
    def test_ascii_gs_does_not_split_csv_code(self) -> None:
        code = "010692181781001621serial\x1d91abcd\x1d92crypto"
        codes = read_codes("codes.csv", (code + "\r\n").encode())
        self.assertEqual(codes, [code])

    def test_recovers_excel_escaped_gs(self) -> None:
        escaped = "010692181781001621serial_x001D_91abcd_x001D_92crypto"
        codes = read_codes("codes.csv", (escaped + "\n").encode())
        self.assertEqual(codes, ["010692181781001621serial\x1d91abcd\x1d92crypto"])

    def test_rejects_partial_marking_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "To'liq Asl Belgisi"):
            create_datamatrix_pdf(["010692181781001621serial"], "Maishiy texnika")

    def test_gs1_escapes_parentheses_inside_serial(self) -> None:
        code = "010692181781001621abc(def)ghi\x1d91liO1\x1d92crypto"
        self.assertEqual(
            normalize_gs1_marking_code(code),
            "(01)06921817810016(21)abc\\(def\\)ghi(91)liO1(92)crypto",
        )

    def test_selects_only_full_marking_codes(self) -> None:
        full = "010692181781001621serial\x1d91abcd\x1d92crypto"
        self.assertEqual(
            select_full_marking_codes(["Код ТН ВЭД", "012", full]),
            [full],
        )

    def test_selects_mineral_fertilizer_codes(self) -> None:
        code = "0104780162800088217(7kGZvz7jtyb\x1d93vW7f"
        self.assertEqual(
            select_full_marking_codes(["012", code], "Mineral o'g'itlar"),
            [code],
        )

    def test_builds_mineral_fertilizer_pdf(self) -> None:
        code = "0104780162800088217(7kGZvz7jtyb\x1d93vW7f"
        pdf = create_datamatrix_pdf([code], "Mineral o'g'itlar")
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
