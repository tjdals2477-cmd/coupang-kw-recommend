"""Packaged configuration loading without a runtime YAML dependency for init."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
import shutil
from typing import Any


def template_path(name: str):
    return files("coupang_kw_rec").joinpath("templates", name)


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    if path:
        text = Path(path).read_text(encoding="utf-8")
    elif Path("recommend.yaml").exists():
        text = Path("recommend.yaml").read_text(encoding="utf-8")
    else:
        text = template_path("recommend.yaml").read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("사용자 YAML을 읽으려면 PyYAML 설치가 필요합니다.") from exc
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise ValueError("설정 루트는 객체여야 합니다.")
        return parsed


def initialize_workdir(target_dir: str | Path, force: bool = False) -> list[Path]:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for source_name, destination_name in (("recommend.yaml", "recommend.yaml"), ("env.example", ".env.example")):
        destination = target / destination_name
        if destination.exists() and not force:
            continue
        with template_path(source_name).open("rb") as source, destination.open("wb") as sink:
            shutil.copyfileobj(source, sink)
        outputs.append(destination)
    return outputs
