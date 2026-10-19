"""清洗 Canonical Record，并生成可幂等写入的数据质量事件。"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from scripts.ingestion.response_normalizer import NormalizedAirQualityRecord

NUMERIC_FIELDS = ("aqi", "pm10", "pm2_5", "so2", "co", "no2", "o3")


@dataclass(frozen=True)
class QualityIssue:
    """一条稳定标识的数据质量发现事件。"""

    issue_key: str
    city: str
    business_date: date
    field_name: str
    issue_code: str
    severity: str
    original_value: str | None
    message: str


@dataclass(frozen=True)
class CleanRecord:
    """写入清洗层的日粒度记录。"""

    source_raw_id: int
    city: str
    business_date: date
    aqi: Decimal | None
    pm10: Decimal | None
    pm2_5: Decimal | None
    so2: Decimal | None
    co: Decimal | None
    no2: Decimal | None
    o3: Decimal | None
    primary_pollutant: str | None
    quality: str | None
    has_missing: bool


def clean_record(
    raw_id: int, record: NormalizedAirQualityRecord
) -> tuple[CleanRecord, list[QualityIssue]]:
    """应用最小质量规则；非法值置空，原始层数据保持不变。"""

    values = asdict(record)
    issues: list[QualityIssue] = []
    for field in NUMERIC_FIELDS:
        value = values[field]
        issue_code = None
        if value is None:
            issue_code = "MISSING"
        elif value < 0 or (field == "aqi" and value > 500):
            issue_code = "OUT_OF_RANGE"
            values[field] = None
        if issue_code:
            original = None if value is None else str(value)
            issues.append(
                _issue(record.city, record.business_date, field, issue_code, original)
            )

    clean = CleanRecord(
        source_raw_id=raw_id,
        city=record.city,
        business_date=record.business_date,
        aqi=values["aqi"], pm10=values["pm10"], pm2_5=values["pm2_5"],
        so2=values["so2"], co=values["co"], no2=values["no2"], o3=values["o3"],
        primary_pollutant=record.primary_pollutant,
        quality=record.quality,
        has_missing=any(values[field] is None for field in NUMERIC_FIELDS),
    )
    return clean, issues


def clean_records(
    records: Iterable[tuple[int, NormalizedAirQualityRecord]],
) -> tuple[list[CleanRecord], list[QualityIssue]]:
    """批量清洗并合并质量事件。"""

    clean_items: list[CleanRecord] = []
    issues: list[QualityIssue] = []
    for raw_id, record in records:
        clean, item_issues = clean_record(raw_id, record)
        clean_items.append(clean)
        issues.extend(item_issues)
    return clean_items, issues


def deduplicate_records(
    records: Iterable[tuple[int, NormalizedAirQualityRecord]],
) -> tuple[list[tuple[int, NormalizedAirQualityRecord]], list[QualityIssue]]:
    """按业务键确定性保留最大来源 ID，并为冲突生成质量事件。

    Raw 层仍保留全部来源记录。来源没有可靠更新时间字段，因此最大来源 ID
    只是可复现的工程规则，不代表数据源业务上的“最新版本”。
    """
    grouped: dict[tuple[str, date], list[tuple[int, NormalizedAirQualityRecord]]] = {}
    for item in records:
        grouped.setdefault((item[1].city, item[1].business_date), []).append(item)

    selected: list[tuple[int, NormalizedAirQualityRecord]] = []
    issues: list[QualityIssue] = []
    for (city, business_date), candidates in sorted(grouped.items()):
        ordered = sorted(candidates, key=lambda item: (item[1].source_id, item[0]))
        selected.append(ordered[-1])
        if len(ordered) > 1:
            source_ids = ",".join(str(item[1].source_id) for item in ordered)
            issues.append(_issue(
                city, business_date, "business_key", "DUPLICATE", source_ids
            ))
    return selected, issues


def _issue(
    city: str, business_date: date, field: str, code: str, original: str | None
) -> QualityIssue:
    identity = f"{city}|{business_date.isoformat()}|{field}|{code}"
    messages = {
        "MISSING": "字段缺失",
        "OUT_OF_RANGE": "字段值超出项目允许范围",
        "DUPLICATE": "同一城市和业务日期存在多条来源记录",
    }
    message = messages[code]
    return QualityIssue(
        issue_key=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        city=city, business_date=business_date, field_name=field,
        issue_code=code, severity="warning", original_value=original, message=message,
    )
