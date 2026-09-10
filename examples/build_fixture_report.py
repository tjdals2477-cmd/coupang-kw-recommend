"""Build a deterministic sample report without calling the real API."""

from __future__ import annotations

import json
from pathlib import Path

from coupang_kw_rec.config import load_config
from coupang_kw_rec.naver_api import Credentials, NaverKeywordClient
from coupang_kw_rec.pipeline import run_pipeline
from coupang_kw_rec.report import write_outputs
from coupang_kw_rec.source import InputData, read_seed_file


class FixtureResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FixtureSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return FixtureResponse(self.payload)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "src" / "coupang_kw_rec" / "templates" / "recommend.yaml")
    payload = json.loads((root / "tests" / "fixtures" / "naver_sample.json").read_text(encoding="utf-8"))
    data = InputData(direct_seeds=read_seed_file(root / "examples" / "seeds.txt"))
    client = NaverKeywordClient(
        Credentials("fixture", "fixture", "fixture"),
        config["naver_api"],
        cache_dir=root / "output" / ".fixture-cache",
        session=FixtureSession(payload),
        clock=lambda: 1_700_000_000,
        sleeper=lambda _: None,
    )
    result = run_pipeline(data, [], config, Credentials("fixture", "fixture", "fixture"), 500, client=client)
    paths = write_outputs(result, config, root / "output")
    print({key: str(path) for key, path in paths.items()})
    print({"recommendations": len(result.recommendations), "api_calls": result.collection.api_calls})


if __name__ == "__main__":
    main()
