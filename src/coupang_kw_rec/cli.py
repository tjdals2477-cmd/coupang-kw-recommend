"""Console entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import initialize_workdir, load_config
from .naver_api import Credentials
from .pipeline import run_pipeline
from .report import write_outputs
from .seed import select_seeds
from .source import InputData, read_core_workbook, read_seed_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coupang-kw-rec", description="쿠팡 키워드 추천 도구")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="설정과 환경변수 예시 파일을 복사합니다.")
    init.add_argument("--dir", default=".", help="초기화할 작업 디렉터리")
    init.add_argument("--force", action="store_true", help="기존 파일을 덮어씁니다.")

    recommend = commands.add_parser("recommend", help="시드를 선정하고 추천 키워드를 수집합니다.")
    recommend.add_argument("--source", help="코어 산출 엑셀")
    recommend.add_argument("--seeds", help="TXT 또는 1열 CSV 시드")
    recommend.add_argument("--limit", type=int, default=500, help="추천 개수, 하드상한 500")
    recommend.add_argument("--offline", action="store_true", help="캐시만 사용하고 네트워크를 호출하지 않습니다.")
    recommend.add_argument("--dry-run", action="store_true", help="API 호출 없이 시드 선정까지만 수행합니다.")
    recommend.add_argument("--config", help="recommend.yaml 경로")
    recommend.add_argument("--out", default="output", help="출력 디렉터리")
    recommend.add_argument("--exclude-keywords", help="등록 제외 키워드 TXT 또는 1열 CSV")
    return parser


def _run_init(args: argparse.Namespace) -> int:
    created = initialize_workdir(args.dir, args.force)
    if created:
        for path in created:
            print(f"생성: {path.resolve()}")
    else:
        print("변경 없음: 기존 파일을 보존했습니다. 덮어쓰려면 --force를 사용하세요.")
    return 0


def _run_recommend(args: argparse.Namespace) -> int:
    if not args.source and not args.seeds:
        print("오류: --source와 --seeds 중 하나 이상이 필요합니다.", file=sys.stderr)
        return 2
    config = load_config(args.config)
    data = read_core_workbook(args.source, config) if args.source else InputData()
    if args.seeds:
        data.direct_seeds.extend(read_seed_file(args.seeds))
    choices = select_seeds(data, config)
    print(f"선정 시드: {len(choices)}개 / 최대 {config['seed_selection']['max_seeds']}개")
    for index, choice in enumerate(choices, start=1):
        print(f"{index:>2}. {choice.keyword}\t{choice.reason}\t{choice.seed_score:g}")
    for warning in data.warnings:
        print(f"경고: {warning}", file=sys.stderr)
    if args.dry_run:
        print("dry-run 완료: 네트워크 호출 0회")
        return 0
    try:
        from dotenv import load_dotenv
        load_dotenv(Path.cwd() / ".env")
    except ImportError:
        pass
    credentials = Credentials.from_env()
    if not args.offline and not credentials.complete:
        print("오류: .env에 네이버 검색광고 API 자격증명 3개를 입력하세요.", file=sys.stderr)
        return 2
    exclusions = read_seed_file(args.exclude_keywords) if args.exclude_keywords else []
    result = run_pipeline(data, exclusions, config, credentials, args.limit, offline=args.offline)
    paths = write_outputs(result, config, args.out)
    print(
        f"완료: 추천 {len(result.recommendations)}개, 보류 {len(result.filters.held)}개, "
        f"역제안 {len(result.filters.reverse_excludes)}개, 수집실패 {len(result.collection.failures)}청크"
    )
    preview_count = config["output"]["console_preview_count"]
    for row in result.recommendations[:preview_count]:
        print(
            f"{row['rank']:>3}. {row['keyword']}\t{row['rec_grade']}\t"
            f"검색량={row.get('search_volume', '')}\t점수={row['score']:.4f}"
        )
    for label, path in paths.items():
        print(f"{label}: {path.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init":
        return _run_init(args)
    return _run_recommend(args)


if __name__ == "__main__":
    raise SystemExit(main())
