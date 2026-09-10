import unittest

from coupang_kw_rec.kwnorm import KWNORM_CONTRACT_VERSION, normalize_keyword, tokenize


CASES = [
    (",led 외견170", "led 외견170"),
    ("1구 매립형 전등 스위치'", "1구 매립형 전등 스위치"),
    ("100  w십자등", "100 w십자등"),
    ("100W LED등", "100w led등"),
    ("120x120 180*125 70 120", "120x120 180*125 70 120"),
]


class KwNormContractTests(unittest.TestCase):
    def test_version_is_explicit(self):
        self.assertEqual(KWNORM_CONTRACT_VERSION, "1.0.0")

    def test_contract_cases(self):
        for raw, expected in CASES:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_keyword(raw), expected)

    def test_token_contract(self):
        self.assertEqual(tokenize("100W  LED등"), ["100w", "led등"])


if __name__ == "__main__":
    unittest.main()
