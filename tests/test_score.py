import unittest

from coupang_kw_rec.config import load_config
from coupang_kw_rec.score import apply_limit, score_keywords


class ScoreTests(unittest.TestCase):
    def test_brand_survives_hard_limit(self):
        config = load_config()
        rows = []
        for index in range(500):
            rows.append({
                "keyword": f"LED조명{index}", "search_volume": 10000 - index,
                "mobile_ratio": 0.5, "seed_score": 10, "seed_count": 1,
                "seed_keywords": ["LED조명"], "comp_idx": "낮음", "brand": "NONE",
            })
        rows.append({
            "keyword": "GONEO LED등", "search_volume": 1, "mobile_ratio": 0,
            "seed_score": 0, "seed_count": 1, "seed_keywords": ["GONEO"],
            "comp_idx": "높음", "brand": "GONEO",
        })
        scored = score_keywords(rows, config)
        limited, trimmed = apply_limit(scored, 500, config)
        self.assertEqual(len(limited), 500)
        self.assertEqual(trimmed, 1)
        self.assertIn("GONEO LED등", [row["keyword"] for row in limited])


if __name__ == "__main__":
    unittest.main()
