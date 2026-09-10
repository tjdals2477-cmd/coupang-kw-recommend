import unittest

from coupang_kw_rec.config import load_config
from coupang_kw_rec.filter import apply_filters, detect_own_brand
from coupang_kw_rec.source import InputData


def row(keyword, volume=100):
    return {"keyword": keyword, "search_volume": volume, "seed_keywords": ["LED등"], "seed_count": 1, "seed_score": 1}


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_own_brand_passes_and_competitor_is_blocked(self):
        result = apply_filters(
            [row("GONEO LED등", 1), row("필립스 LED등")],
            InputData(),
            [],
            self.config,
        )
        self.assertEqual([item["brand"] for item in result.candidates], ["GONEO"])
        self.assertEqual(result.rejected[0]["reason"], "타사 브랜드: 필립스")

    def test_ant_does_not_match_inside_english_words(self):
        self.assertEqual(detect_own_brand("pendant light", self.config), "NONE")
        self.assertEqual(detect_own_brand("plant grow led", self.config), "NONE")
        self.assertEqual(detect_own_brand("ANT LED등", self.config), "ANT")

    def test_absent_feature_becomes_reverse_exclusion(self):
        result = apply_filters([row("LED 센서등")], InputData(), [], self.config)
        self.assertEqual(len(result.reverse_excludes), 1)
        self.assertIn("센서", result.reverse_excludes[0]["reason"])

    def test_generic_product_is_not_held_by_electrical_category_words(self):
        result = apply_filters([row("안경테")], InputData(direct_seeds=["안경"]), [], self.config)
        self.assertEqual([item["keyword"] for item in result.candidates], ["안경테"])
        self.assertEqual(result.held, [])


if __name__ == "__main__":
    unittest.main()
