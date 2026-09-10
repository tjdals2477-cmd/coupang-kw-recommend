from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest

from coupang_kw_rec.app import HELD_COLUMN_LABELS, recommendations_for_display, rows_for_display


class StreamlitAppTests(unittest.TestCase):
    def test_recommendation_columns_are_korean_and_readable(self):
        displayed = recommendations_for_display([
            {
                "rank": 1,
                "keyword": "LED일자등",
                "rec_grade": "REC_A_즉시등록",
                "score": 0.42,
                "mobile_ratio": 0.625,
                "relevance": 1.0,
                "brand": "NONE",
                "already_converting": False,
            }
        ])[0]
        self.assertEqual(displayed["추천 키워드"], "LED일자등")
        self.assertEqual(displayed["추천 등급"], "A · 바로 등록")
        self.assertEqual(displayed["추천 종합점수(100점)"], 100.0)
        self.assertEqual(displayed["모바일 비중(%)"], 62.5)
        self.assertEqual(displayed["상품명 연관도(%)"], 100.0)
        self.assertEqual(displayed["브랜드 구분"], "일반 키워드")
        self.assertEqual(displayed["기존 전환 키워드"], "아니오")

    def test_score_is_normalized_to_one_hundred_points(self):
        displayed = recommendations_for_display([
            {"keyword": "상", "score": 0.8},
            {"keyword": "중", "score": 0.5},
            {"keyword": "하", "score": 0.2},
        ])
        self.assertEqual([row["추천 종합점수(100점)"] for row in displayed], [100.0, 50.0, 0.0])

    def test_held_keywords_have_korean_columns(self):
        displayed = rows_for_display(
            [{"keyword": "의심키워드", "reason": "브랜드 의심: 샘플", "search_volume": 120}],
            HELD_COLUMN_LABELS,
        )[0]
        self.assertEqual(displayed["보류 키워드"], "의심키워드")
        self.assertEqual(displayed["보류 이유"], "브랜드 의심: 샘플")
        self.assertEqual(displayed["월간 총검색량"], 120)

    def test_seed_only_user_flow(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.secrets["APP_PASSWORD"] = "test-password"
        app.run(timeout=20)
        self.assertEqual(app.text_input[0].label, "앱 비밀번호")
        app.text_input[0].input("test-password")
        app.button[0].click().run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "쿠팡 키워드 추천")
        app.text_area[0].input("데이온 LED 일자등 30W\nLED 일자등")
        app.checkbox[1].check()
        app.button[0].click().run(timeout=20)
        self.assertFalse(app.exception)
        self.assertIn("네트워크 호출은 0회", app.success[0].value)


if __name__ == "__main__":
    unittest.main()
