from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
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
