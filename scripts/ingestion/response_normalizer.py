"""将已保存的来源响应转换为确定性的 Canonical Record。

本模块只处理内存中的 JSON 记录，不访问网络、文件系统或数据库。所有记录
通过校验后才返回结果；任一记录失败时调用方不会得到部分可导入数据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence


SHANGHAI_FIXED_OFFSET = timezone(timedelta(hours=8), name="UTC+08:00")
DOTNET_DATE_PATTERN = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")

CITY_CONTRACT = {
    "110000": ("北京", "北京市"),
    "310000": ("上海", "上海市"),
    "440100": ("广州", "广州市"),
    "510100": ("成都", "成都市"),
    "420100": ("武汉", "武汉市"),
}

NUMERIC_FIELD_MAP = {
    "AQI": "aqi",
    "PM10_24h": "pm10",
    "PM2_5_24h": "pm2_5",
    "SO2_24h": "so2",
    "CO_24h": "co",
    "NO2_24h": "no2",
    "O3_8h_24h": "o3",
}

REQUIRED_SOURCE_FIELDS = frozenset(
    {
        "Id",
        "CityCode",
        "TimePoint",
        "TimePointStr",
        "Area",
        *NUMERIC_FIELD_MAP,
        "PrimaryPollutant",
        "Quality",
        "Unheathful",
        "Measure",
    }
)


class ResponseNormalizationError(ValueError):
    """表示来源记录不满足已校准的响应 Contract。"""


@dataclass(frozen=True)
class NormalizedAirQualityRecord:
    """可供后续 Raw Loader 使用的日级规范化记录。

    数值字段使用 ``Decimal``，避免在写入 MySQL 前引入二进制浮点误差。
    当前阶段不附加污染物单位，因为可靠单位证据仍为 ``UNKNOWN``。
    """

    source_id: int
    city_code: str
    city: str
    source_area: str
    business_date: date
    source_time_point: str
    source_time_point_text: str | None
    aqi: Decimal | None
    pm10: Decimal | None
    pm2_5: Decimal | None
    so2: Decimal | None
    co: Decimal | None
    no2: Decimal | None
    o3: Decimal | None
    primary_pollutant: str | None
    quality: str | None
    health_advice: str | None
    activity_advice: str | None
    source_type: str = "cnemc_api"
    source_record_key: str | None = None
    observation_hour: int | None = None
    source_file: str | None = None


def parse_dotnet_business_date(value: object) -> date:
    """将 ``/Date(epoch_ms)/`` 确定性转换为 UTC+08:00 业务日期。

    Microsoft JSON Date 中的毫秒数表示 UTC Epoch；可选的 ``+0800`` 后缀仅是
    显示偏移，不参与 Epoch 计算。显式固定 UTC+08:00 可避免依赖主机时区，且
    当前项目只处理现代中国空气质量数据，不需要历史夏令时规则。

    Raises:
        ResponseNormalizationError: 输入格式、偏移或时间范围非法。
    """

    if not isinstance(value, str):
        raise ResponseNormalizationError("TimePoint 必须是 /Date(epoch_ms)/ 字符串")

    match = DOTNET_DATE_PATTERN.fullmatch(value.strip())
    if not match:
        raise ResponseNormalizationError(f"TimePoint 格式非法: {value!r}")

    offset_text = match.group(2)
    if offset_text:
        offset_hour = int(offset_text[1:3])
        offset_minute = int(offset_text[3:5])
        if offset_hour > 23 or offset_minute > 59:
            raise ResponseNormalizationError(f"TimePoint 偏移非法: {value!r}")

    try:
        instant_utc = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            milliseconds=int(match.group(1))
        )
    except (OverflowError, ValueError) as exc:
        raise ResponseNormalizationError(f"TimePoint 超出可解析范围: {value!r}") from exc

    return instant_utc.astimezone(SHANGHAI_FIXED_OFFSET).date()


def normalize_records(
    records: Sequence[Mapping[str, object]],
) -> list[NormalizedAirQualityRecord]:
    """校验并规范化一个来源批次，按业务日期和来源 ID 确定性排序。

    同一批次中的 ``Id`` 或 ``(city, business_date)`` 重复会整体失败。当前没有
    可靠证据支持静默选择某一条，因此将冲突留给后续 Raw Schema 决策处理。

    Raises:
        ResponseNormalizationError: 批次为空、记录字段/类型非法或出现重复键。
    """

    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise ResponseNormalizationError("来源响应必须是记录列表")
    if not records:
        raise ResponseNormalizationError("来源响应记录列表不能为空")

    normalized: list[NormalizedAirQualityRecord] = []
    source_ids: set[int] = set()
    business_keys: set[tuple[str, date]] = set()

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise ResponseNormalizationError(f"第 {index} 条记录不是 JSON Object")

        item = _normalize_record(record, index=index)
        if item.source_id in source_ids:
            raise ResponseNormalizationError(f"来源 Id 重复: {item.source_id}")

        business_key = (item.city, item.business_date)
        if business_key in business_keys:
            raise ResponseNormalizationError(
                "业务键重复: "
                f"city={item.city}, business_date={item.business_date.isoformat()}"
            )

        source_ids.add(item.source_id)
        business_keys.add(business_key)
        normalized.append(item)

    return sorted(normalized, key=lambda item: (item.business_date, item.source_id))


def _normalize_record(
    record: Mapping[str, object], *, index: int
) -> NormalizedAirQualityRecord:
    missing_fields = sorted(REQUIRED_SOURCE_FIELDS.difference(record))
    if missing_fields:
        raise ResponseNormalizationError(
            f"第 {index} 条记录缺少必要字段: {', '.join(missing_fields)}"
        )

    source_id = _parse_source_id(record["Id"], index=index)
    city_code = _parse_city_code(record["CityCode"], index=index)
    city, expected_area = CITY_CONTRACT[city_code]
    source_area = _required_text(record["Area"], field="Area", index=index)
    if source_area != expected_area:
        raise ResponseNormalizationError(
            f"第 {index} 条记录 CityCode 与 Area 不匹配: "
            f"{city_code}/{source_area}"
        )

    numeric_values = {
        canonical_name: _parse_optional_decimal(
            record[source_name], field=source_name, index=index
        )
        for source_name, canonical_name in NUMERIC_FIELD_MAP.items()
    }
    source_time_point = _required_text(
        record["TimePoint"], field="TimePoint", index=index
    )

    return NormalizedAirQualityRecord(
        source_id=source_id,
        city_code=city_code,
        city=city,
        source_area=source_area,
        business_date=parse_dotnet_business_date(source_time_point),
        source_time_point=source_time_point,
        source_time_point_text=_optional_text(
            record["TimePointStr"], field="TimePointStr", index=index
        ),
        primary_pollutant=_optional_text(
            record["PrimaryPollutant"], field="PrimaryPollutant", index=index
        ),
        quality=_optional_text(record["Quality"], field="Quality", index=index),
        health_advice=_optional_text(
            record["Unheathful"], field="Unheathful", index=index
        ),
        activity_advice=_optional_text(
            record["Measure"], field="Measure", index=index
        ),
        source_record_key=f"cnemc_api:{city_code}:{source_id}",
        **numeric_values,
    )


def _parse_source_id(value: object, *, index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ResponseNormalizationError(f"第 {index} 条记录 Id 必须是正整数")
    return value


def _parse_city_code(value: object, *, index: int) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ResponseNormalizationError(f"第 {index} 条记录 CityCode 类型非法")
    city_code = str(value).strip()
    if city_code not in CITY_CONTRACT:
        raise ResponseNormalizationError(
            f"第 {index} 条记录 CityCode 不在允许范围内: {city_code}"
        )
    return city_code


def _parse_optional_decimal(
    value: object, *, field: str, index: int
) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ResponseNormalizationError(f"第 {index} 条记录 {field} 类型非法")

    try:
        parsed = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ResponseNormalizationError(
            f"第 {index} 条记录 {field} 不是有效数值: {value!r}"
        ) from exc
    if not parsed.is_finite():
        raise ResponseNormalizationError(
            f"第 {index} 条记录 {field} 必须是有限数值"
        )
    return parsed


def _required_text(value: object, *, field: str, index: int) -> str:
    parsed = _optional_text(value, field=field, index=index)
    if parsed is None:
        raise ResponseNormalizationError(f"第 {index} 条记录 {field} 不能为空")
    return parsed


def _optional_text(value: object, *, field: str, index: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ResponseNormalizationError(f"第 {index} 条记录 {field} 必须是字符串")
    return value.strip() or None
