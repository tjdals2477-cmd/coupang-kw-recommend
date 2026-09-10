import base64
import hashlib
import hmac
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from coupang_kw_rec.config import load_config
from coupang_kw_rec.naver_api import Credentials, NaverKeywordClient, make_signature, parse_metric
from coupang_kw_rec.seed import SeedChoice


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class NaverApiTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()["naver_api"]
        self.payload = json.loads((Path(__file__).parent / "fixtures" / "naver_sample.json").read_text(encoding="utf-8"))
        self.credentials = Credentials("api", "secret", "123")

    def test_metric_parsing(self):
        self.assertEqual(parse_metric("< 10", 5), 5)
        self.assertEqual(parse_metric("1,234", 5), 1234)
        self.assertTrue(math.isnan(parse_metric(None, 5)))
        self.assertTrue(math.isnan(parse_metric("알수없음", 5)))

    def test_signature_is_reproducible(self):
        timestamp = "1700000000000"
        message = f"{timestamp}.GET./keywordstool".encode()
        expected = base64.b64encode(hmac.new(b"secret", message, hashlib.sha256).digest()).decode()
        self.assertEqual(make_signature(timestamp, "GET", "/keywordstool", "secret"), expected)

    def test_retry_failure_does_not_stop_next_chunk(self):
        session = Mock()
        session.get.side_effect = [
            FakeResponse(429, text="busy"),
            FakeResponse(500, text="server"),
            FakeResponse(500, text="server"),
            FakeResponse(500, text="server"),
            FakeResponse(200, self.payload),
        ]
        seeds = [SeedChoice(f"seed{i}", "test", 1) for i in range(6)]
        with tempfile.TemporaryDirectory() as directory:
            client = NaverKeywordClient(self.credentials, self.config, directory, session, clock=lambda: 1700000000, sleeper=lambda _: None)
            result = client.collect(seeds)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.successful_chunks, 1)
        self.assertEqual(len(result.candidates), 2)

    def test_offline_never_calls_network(self):
        session = Mock()
        with tempfile.TemporaryDirectory() as directory:
            client = NaverKeywordClient(self.credentials, self.config, directory, session, clock=lambda: 1700000000, sleeper=lambda _: None)
            result = client.collect([SeedChoice("LED등", "test", 1)], offline=True)
        session.get.assert_not_called()
        self.assertEqual(result.failures[0]["status"], "OFFLINE_CACHE_MISS")


if __name__ == "__main__":
    unittest.main()
