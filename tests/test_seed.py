import unittest

from coupang_kw_rec.config import load_config
from coupang_kw_rec.seed import select_seeds
from coupang_kw_rec.source import InputData


class SeedSelectionTests(unittest.TestCase):
    def test_direct_seeds_are_deduplicated_and_brands_are_forced(self):
        config = load_config()
        data = InputData(direct_seeds=["LED 일자등", "led 일자등", "센서등"])
        result = select_seeds(data, config)
        normalized = [item.keyword.casefold() for item in result]
        self.assertEqual(normalized.count("led 일자등"), 1)
        for brand in ["goneo", "고네오", "dayon", "데이온", "ant", "안트", "dnn", "디앤앤"]:
            self.assertIn(brand, normalized)


if __name__ == "__main__":
    unittest.main()
