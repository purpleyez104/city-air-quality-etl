"""多城市空气质量 ETL 的统一命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.config import ConfigurationError, load_mysql_settings
from scripts.ingestion.snapshot_loader import load_snapshot
from scripts.ingestion.source_probe import CITY_NAMES_BY_CODE, SourceProbeError, run_probe
from scripts.pipeline import run_etl
from scripts.reporting.dashboard import generate_dashboard
from scripts.storage.mysql_repository import MySQLRepository, RepositoryError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="多城市空气质量采集、ETL 与报告工具")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="创建缺失的项目自有 MySQL 表")
    collect = commands.add_parser("collect", help="执行显式授权的 Source Probe")
    collect.add_argument("--execute", action="store_true", help="确认发送网络请求")
    collect.add_argument("--cities", nargs="+", choices=sorted(CITY_NAMES_BY_CODE), required=True)
    collect.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    load = commands.add_parser("load", help="校验 Snapshot 并导入 Raw 层")
    load.add_argument("--batch-dir", type=Path, required=True)
    run = commands.add_parser("run", help="执行 Raw 到 Clean 的 ETL")
    run.add_argument("--batch-id")
    report = commands.add_parser("report", help="从 Clean 层生成 Dashboard")
    report.add_argument("--output-dir", type=Path, default=Path("outputs/latest"))
    preview = commands.add_parser("preview", help="从 Snapshot 生成不写数据库的展示报告")
    preview.add_argument("--batch-dirs", nargs="+", type=Path, required=True)
    preview.add_argument("--output-dir", type=Path, default=Path("outputs/preview"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "collect":
            if not args.execute:
                print("未提供 --execute：未发送网络请求。", file=sys.stderr)
                return 2
            results = [run_probe(code, args.output_dir) for code in args.cities]
            print(json.dumps([result.manifest for result in results], ensure_ascii=False, default=str))
            return 0

        if args.command == "preview":
            from dataclasses import asdict
            from scripts.processing.quality import clean_record

            clean_rows = []
            issue_rows = []
            raw_id = 0
            for batch_dir in args.batch_dirs:
                _, records = load_snapshot(batch_dir)
                for record in records:
                    raw_id += 1
                    clean, issues = clean_record(raw_id, record)
                    clean_rows.append(asdict(clean))
                    issue_rows.extend(asdict(issue) for issue in issues)
            paths = generate_dashboard(clean_rows, issue_rows, args.output_dir)
            print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False))
            return 0

        repository = MySQLRepository(load_mysql_settings())
        if args.command == "init":
            repository.initialize_schema(Path("sql/schema.sql"))
            print("项目 MySQL Schema 初始化完成。")
        elif args.command == "load":
            batch_id, records = load_snapshot(args.batch_dir)
            count = repository.upsert_raw(batch_id, records)
            print(json.dumps({"batch_id": batch_id, "loaded_count": count}, ensure_ascii=False))
        elif args.command == "run":
            print(json.dumps(run_etl(repository, args.batch_id), ensure_ascii=False))
        elif args.command == "report":
            clean, issues = repository.fetch_dashboard_data()
            paths = generate_dashboard(clean, issues, args.output_dir)
            print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False))
        return 0
    except (ConfigurationError, RepositoryError, SourceProbeError, ValueError, OSError) as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
