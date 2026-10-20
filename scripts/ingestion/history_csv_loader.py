"""将 QuotSoft 全国城市小时 CSV 转换为五城市日粒度 Raw Record。"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.ingestion.response_normalizer import CITY_CONTRACT, NormalizedAirQualityRecord

HISTORY_SOURCE_TYPE = "quotsoft_history_csv"
TARGET_HOUR = 23
FILE_PATTERN = re.compile(r"^china_cities_(\d{8})\.csv$")
CSV_TYPE_MAP = {
    "AQI": "aqi",
    "PM10_24h": "pm10",
    "PM2.5_24h": "pm2_5",
    "SO2_24h": "so2",
    "CO_24h": "co",
    "NO2_24h": "no2",
    "O3_8h_24h": "o3",
}
CITY_CODE_BY_NAME = {city: code for code, (city, _) in CITY_CONTRACT.items()}
SOURCE_AREA_BY_NAME = {city: area for _, (city, area) in CITY_CONTRACT.items()}


class HistoryCsvError(ValueError):
    """表示历史 CSV 不满足当前项目确认的数据 Contract。"""


@dataclass(frozen=True)
class HistoryLoadResult:
    """历史 CSV 转换结果及可用于验收的汇总统计。"""

    batch_id: str
    records: list[NormalizedAirQualityRecord]
    file_count: int
    date_min: date
    date_max: date
    fallback_count: int
    missing_value_count: int
    source_bytes: int
    source_sha256: str


def load_history_csv(input_dir: Path) -> HistoryLoadResult:
    """校验目录内全部日文件并转换，不访问网络或数据库。

    每个城市每天固定优先 23 时。只有 23 时的 Canonical 指标行全部不存在时，
    才回退到当天存在指标行的最晚小时。字段空值保留为 ``None``，不跨小时填充。

    Raises:
        HistoryCsvError: 文件缺失、Schema 漂移、日期不一致或字段非法。
    """

    root = Path(input_dir)
    files = sorted(
        path
        for path in root.rglob("china_cities_*.csv")
        if not path.name.startswith("._")
    )
    if not files:
        raise HistoryCsvError(f"未找到 china_cities_YYYYMMDD.csv: {root}")

    records: list[NormalizedAirQualityRecord] = []
    dates: list[date] = []
    fallback_count = 0
    missing_value_count = 0
    source_bytes = 0
    digest = hashlib.sha256()
    expected_header: tuple[str, ...] | None = None

    for path in files:
        match = FILE_PATTERN.fullmatch(path.name)
        if not match:
            raise HistoryCsvError(f"历史文件名格式非法: {path.name}")
        file_date = _parse_date(match.group(1), path)
        payload = path.read_bytes()
        source_bytes += len(payload)
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)

        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HistoryCsvError(f"CSV 不是 UTF-8 编码: {path}") from exc

        rows = csv.reader(text.splitlines())
        try:
            header = next(rows)
        except StopIteration as exc:
            raise HistoryCsvError(f"CSV 为空: {path}") from exc
        header_tuple = tuple(header)
        if expected_header is None:
            expected_header = header_tuple
        elif header_tuple != expected_header:
            raise HistoryCsvError(f"CSV Header 漂移: {path}")
        _validate_header(header, path)

        city_indexes = {city: header.index(city) for city in CITY_CODE_BY_NAME}
        by_hour: dict[int, dict[str, list[str]]] = {}
        for line_number, row in enumerate(rows, start=2):
            if len(row) != len(header):
                raise HistoryCsvError(f"CSV 列数非法: {path}:{line_number}")
            if row[0] != match.group(1):
                raise HistoryCsvError(f"文件名日期与 date 不一致: {path}:{line_number}")
            try:
                hour = int(row[1])
            except ValueError as exc:
                raise HistoryCsvError(f"hour 不是整数: {path}:{line_number}") from exc
            if not 0 <= hour <= 23:
                raise HistoryCsvError(f"hour 超出 0-23: {path}:{line_number}")
            metric_type = row[2].strip()
            if metric_type not in CSV_TYPE_MAP:
                continue
            hour_values = by_hour.setdefault(hour, {})
            if metric_type in hour_values:
                raise HistoryCsvError(
                    f"同一小时指标重复: {path}:{line_number} "
                    f"hour={hour} type={metric_type}"
                )
            hour_values[metric_type] = row

        if not by_hour:
            raise HistoryCsvError(f"文件没有 Canonical 指标: {path}")
        selected_hour = TARGET_HOUR if TARGET_HOUR in by_hour else max(by_hour)
        is_fallback = selected_hour != TARGET_HOUR
        values_at_hour = by_hour[selected_hour]
        for city, city_index in city_indexes.items():
            numeric_values: dict[str, Decimal | None] = {}
            for source_type, canonical_name in CSV_TYPE_MAP.items():
                row = values_at_hour.get(source_type)
                raw_value = None if row is None else row[city_index]
                value = _parse_decimal(
                    raw_value, path, selected_hour, source_type, city
                )
                numeric_values[canonical_name] = value
                if value is None:
                    missing_value_count += 1

            city_code = CITY_CODE_BY_NAME[city]
            source_key = f"{HISTORY_SOURCE_TYPE}:{city_code}:{file_date.isoformat()}"
            records.append(
                NormalizedAirQualityRecord(
                    source_id=-int(match.group(1)),
                    city_code=city_code,
                    city=city,
                    source_area=SOURCE_AREA_BY_NAME[city],
                    business_date=file_date,
                    source_time_point=(
                        f"{file_date.isoformat()}T{selected_hour:02d}:00:00+08:00"
                    ),
                    source_time_point_text=f"{selected_hour:02d}:00",
                    primary_pollutant=None,
                    quality=None,
                    health_advice=None,
                    activity_advice=None,
                    source_type=HISTORY_SOURCE_TYPE,
                    source_record_key=source_key,
                    observation_hour=selected_hour,
                    source_file=path.name,
                    **numeric_values,
                )
            )
            if is_fallback:
                fallback_count += 1
        dates.append(file_date)

    if len(set(dates)) != len(dates):
        raise HistoryCsvError("存在重复日期文件")
    date_min, date_max = min(dates), max(dates)
    batch_id = f"history-csv-{date_min:%Y%m%d}-{date_max:%Y%m%d}"
    return HistoryLoadResult(
        batch_id=batch_id,
        records=sorted(records, key=lambda item: (item.business_date, item.city_code)),
        file_count=len(files),
        date_min=date_min,
        date_max=date_max,
        fallback_count=fallback_count,
        missing_value_count=missing_value_count,
        source_bytes=source_bytes,
        source_sha256=digest.hexdigest(),
    )


def _validate_header(header: list[str], path: Path) -> None:
    if header[:3] != ["date", "hour", "type"]:
        raise HistoryCsvError(f"CSV 前三列必须是 date,hour,type: {path}")
    missing_cities = sorted(set(CITY_CODE_BY_NAME).difference(header))
    if missing_cities:
        raise HistoryCsvError(f"CSV 缺少目标城市: {path}: {', '.join(missing_cities)}")
    if len(header) != len(set(header)):
        raise HistoryCsvError(f"CSV Header 存在重复列: {path}")


def _parse_date(value: str, path: Path) -> date:
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError as exc:
        raise HistoryCsvError(f"文件日期非法: {path.name}") from exc


def _parse_decimal(
    value: str | None,
    path: Path,
    hour: int,
    metric_type: str,
    city: str,
) -> Decimal | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise HistoryCsvError(
            f"指标不是有效数值: {path.name} hour={hour} "
            f"type={metric_type} city={city}"
        ) from exc
    if not parsed.is_finite():
        raise HistoryCsvError(
            f"指标必须是有限数值: {path.name} hour={hour} "
            f"type={metric_type} city={city}"
        )
    return parsed
