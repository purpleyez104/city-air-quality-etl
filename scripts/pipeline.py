"""连接 MySQL Raw 层、清洗规则与 Clean 层的 ETL 编排。"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from scripts.ingestion.response_normalizer import NormalizedAirQualityRecord
from scripts.processing.quality import clean_records, deduplicate_records
from scripts.storage.mysql_repository import MySQLRepository


def run_etl(repository: MySQLRepository, batch_id: str | None = None) -> dict[str, Any]:
    """执行一次可追踪 ETL；失败时尽力记录失败状态后继续抛出异常。"""
    run_id = str(uuid.uuid4())
    repository.start_run(run_id, batch_id)
    try:
        rows = repository.fetch_raw(batch_id)
        normalized = [(int(row["raw_id"]), _from_raw_row(row)) for row in rows]
        selected, duplicate_issues = deduplicate_records(normalized)
        clean, issues = clean_records(selected)
        issues = duplicate_issues + issues
        output_count = repository.upsert_clean(run_id, clean)
        issue_count = repository.upsert_issues(run_id, issues)
        repository.finish_run(run_id, len(rows), output_count, issue_count)
        return {
            "run_id": run_id, "input_count": len(rows),
            "output_count": output_count, "issue_count": issue_count,
        }
    except Exception as exc:
        try:
            repository.fail_run(run_id, str(exc))
        finally:
            raise


def _from_raw_row(row: dict[str, Any]) -> NormalizedAirQualityRecord:
    """将数据库行恢复为规范化对象，避免 ETL 依赖来源 JSON。"""
    def decimal(name: str) -> Decimal | None:
        value = row[name]
        return None if value is None else Decimal(str(value))

    source_time = row["source_time_point"]
    business_date = row["business_date"]
    if isinstance(business_date, datetime):
        business_date = business_date.date()
    return NormalizedAirQualityRecord(
        source_id=int(row["source_id"]), city_code=str(row["city_code"]),
        city=str(row["city"]), source_area=str(row["source_area"]),
        business_date=business_date, source_time_point=str(source_time),
        source_time_point_text=row.get("source_time_point_text"),
        aqi=decimal("aqi"), pm10=decimal("pm10"), pm2_5=decimal("pm2_5"),
        so2=decimal("so2"), co=decimal("co"), no2=decimal("no2"), o3=decimal("o3"),
        primary_pollutant=row.get("primary_pollutant"), quality=row.get("quality"),
        health_advice=row.get("health_advice"), activity_advice=row.get("activity_advice"),
    )
