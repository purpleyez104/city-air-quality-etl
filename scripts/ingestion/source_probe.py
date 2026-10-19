"""单城市空气质量 Source Probe 与不可变 Raw Snapshot 持久化。

该模块只负责验证候选数据源并保存原始响应，不连接 MySQL，也不执行
ETL。命令行必须显式传入 ``--execute`` 才会发送一次网络请求。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


CANDIDATE_API_URL = (
    "https://air.cnemc.cn:18007/HourChangesPublish/"
    "GetCityDayAqiHistoryByCondition"
)
REFERER = "https://air.cnemc.cn:18007/"
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
ALLOWED_SOURCE_DOMAIN = "cnemc.cn"

CITY_NAMES_BY_CODE = {
    "110000": "北京",
    "310000": "上海",
    "440100": "广州",
    "510100": "成都",
    "420100": "武汉",
}

REQUIRED_RESPONSE_FIELDS = frozenset(
    {
        "Id",
        "CityCode",
        "TimePoint",
        "TimePointStr",
        "Area",
        "AQI",
        "PM10_24h",
        "PM2_5_24h",
        "SO2_24h",
        "CO_24h",
        "NO2_24h",
        "O3_8h_24h",
        "PrimaryPollutant",
        "Quality",
        "Unheathful",
        "Measure",
    }
)


class SourceProbeError(RuntimeError):
    """表示 Source Probe 的请求、校验或落盘失败。"""


@dataclass(frozen=True)
class ProbeResponse:
    """一次 Source Probe 返回且尚未落盘的原始响应。"""

    status: int
    content_type: str
    body: bytes
    final_url: str


@dataclass(frozen=True)
class SnapshotResult:
    """成功落盘后的 Snapshot 路径与 Manifest 内容。"""

    batch_dir: Path
    raw_path: Path
    manifest_path: Path
    manifest: Mapping[str, object]


Opener = Callable[..., object]


def fetch_city_response(
    city_code: str,
    *,
    endpoint: str = CANDIDATE_API_URL,
    timeout_seconds: float = 30.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    opener: Opener = urlopen,
) -> ProbeResponse:
    """向候选接口发送一次单城市请求并返回受大小限制的原始响应。

    Args:
        city_code: 五城市白名单中的行政代码。
        endpoint: 待验证的候选接口 URL。
        timeout_seconds: 单次 HTTP 请求超时秒数，必须大于 0。
        max_response_bytes: 允许读取的最大响应字节数，必须大于 0。
        opener: 兼容 ``urllib.request.urlopen`` 的调用对象，供测试注入。

    Raises:
        SourceProbeError: 参数非法、网络失败、HTTP 失败或响应超限。
    """

    if city_code not in CITY_NAMES_BY_CODE:
        raise SourceProbeError(f"城市代码不在允许范围内: {city_code}")
    if timeout_seconds <= 0:
        raise SourceProbeError("timeout_seconds 必须大于 0")
    if max_response_bytes <= 0:
        raise SourceProbeError("max_response_bytes 必须大于 0")
    _validate_source_url(endpoint)

    request = Request(
        endpoint,
        data=urlencode({"citycode": city_code}).encode("ascii"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
            "User-Agent": "city-air-quality-etl-source-probe/0.1",
        },
        method="POST",
    )

    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", response.getcode()))
            content_type = response.headers.get("Content-Type", "")
            body = response.read(max_response_bytes + 1)
            final_url = response.geturl()
    except HTTPError as exc:
        raise SourceProbeError(f"Source Probe HTTP 失败: status={exc.code}") from exc
    except URLError as exc:
        raise SourceProbeError(f"Source Probe 网络失败: {exc.reason}") from exc
    except OSError as exc:
        raise SourceProbeError(f"Source Probe I/O 失败: {exc}") from exc

    if not 200 <= status < 300:
        raise SourceProbeError(f"Source Probe 返回非成功状态: {status}")
    if len(body) > max_response_bytes:
        raise SourceProbeError(
            f"响应超过大小限制: limit={max_response_bytes} bytes"
        )
    _validate_source_url(final_url)

    return ProbeResponse(
        status=status,
        content_type=content_type,
        body=body,
        final_url=final_url,
    )


def validate_response(response: ProbeResponse) -> int:
    """验证 Content-Type、JSON Shape 和历史字段集合，返回记录数。

    字段值允许为空，因为缺失值属于后续数据质量处理范围；本层只确保
    响应仍符合可识别的记录结构，避免把 HTML 错误页等内容保存为成功数据。
    """

    media_type = response.content_type.partition(";")[0].strip().lower()
    if media_type not in {"application/json", "text/json"} and not media_type.endswith(
        "+json"
    ):
        raise SourceProbeError(
            f"响应 Content-Type 不是 JSON: {response.content_type!r}"
        )

    try:
        payload = json.loads(response.body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceProbeError("响应正文不是有效 UTF-8 JSON") from exc

    if not isinstance(payload, list) or not payload:
        raise SourceProbeError("响应 JSON 必须是非空记录列表")

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise SourceProbeError(f"第 {index} 条记录不是 JSON Object")
        missing_fields = sorted(REQUIRED_RESPONSE_FIELDS.difference(item))
        if missing_fields:
            raise SourceProbeError(
                f"第 {index} 条记录缺少必要字段: {', '.join(missing_fields)}"
            )

    return len(payload)


def persist_snapshot(
    response: ProbeResponse,
    city_code: str,
    output_root: Path,
    *,
    requested_at: datetime | None = None,
    batch_id: str | None = None,
) -> SnapshotResult:
    """验证并以批次目录原子保存 Raw JSON 与 Manifest。

    先在同一父目录的临时目录中写完两个文件，再将整个目录原子改名。
    任一步失败都会清理临时目录，且不会生成成功批次目录。
    """

    if city_code not in CITY_NAMES_BY_CODE:
        raise SourceProbeError(f"城市代码不在允许范围内: {city_code}")

    record_count = validate_response(response)
    requested_at = requested_at or datetime.now(timezone.utc)
    if requested_at.tzinfo is None:
        raise SourceProbeError("requested_at 必须包含时区")

    requested_at_utc = requested_at.astimezone(timezone.utc)
    resolved_batch_id = batch_id or _new_batch_id(requested_at_utc)
    if not _is_safe_batch_id(resolved_batch_id):
        raise SourceProbeError("batch_id 只能包含字母、数字、点、下划线和连字符")

    output_root = Path(output_root)
    final_dir = output_root / resolved_batch_id
    if final_dir.exists():
        raise SourceProbeError(f"批次目录已存在，拒绝覆盖: {final_dir}")

    raw_filename = f"{city_code}.json"
    raw_sha256 = hashlib.sha256(response.body).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "batch_id": resolved_batch_id,
        "requested_at": requested_at_utc.isoformat().replace("+00:00", "Z"),
        "city_code": city_code,
        "city_name": CITY_NAMES_BY_CODE[city_code],
        "request": {
            "method": "POST",
            "endpoint": _redact_url(response.final_url),
            "form_fields": ["citycode"],
        },
        "response": {
            "status": response.status,
            "content_type": response.content_type,
            "record_count": record_count,
            "byte_count": len(response.body),
            "raw_file": raw_filename,
            "sha256": raw_sha256,
        },
    }

    staging_dir = output_root / f".{resolved_batch_id}.tmp-{uuid.uuid4().hex}"

    try:
        output_root.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir()
        (staging_dir / raw_filename).write_bytes(response.body)
        (staging_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(staging_dir, final_dir)
    except OSError as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise SourceProbeError(f"Raw Snapshot 落盘失败: {exc}") from exc

    return SnapshotResult(
        batch_dir=final_dir,
        raw_path=final_dir / raw_filename,
        manifest_path=final_dir / "manifest.json",
        manifest=manifest,
    )


def verify_snapshot(raw_path: Path, expected_sha256: str) -> None:
    """核对 Raw 文件 SHA-256，不一致时拒绝继续处理。"""

    actual_sha256 = hashlib.sha256(Path(raw_path).read_bytes()).hexdigest()
    if not hmac.compare_digest(actual_sha256, expected_sha256.lower()):
        raise SourceProbeError(
            f"Raw Snapshot SHA-256 不匹配: file={Path(raw_path).name}"
        )


def run_probe(
    city_code: str,
    output_root: Path,
    *,
    endpoint: str = CANDIDATE_API_URL,
    timeout_seconds: float = 30.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> SnapshotResult:
    """执行一次单城市请求并保存 Snapshot；该流程不会连接 MySQL。"""

    response = fetch_city_response(
        city_code,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
    )
    return persist_snapshot(response, city_code, output_root)


def _new_batch_id(requested_at_utc: datetime) -> str:
    timestamp = requested_at_utc.strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _is_safe_batch_id(value: str) -> bool:
    return bool(value) and all(
        character.isalnum() or character in {"-", "_", "."}
        for character in value
    )


def _validate_source_url(url: str) -> None:
    """限制 Probe 只访问 CNEMC 的 HTTPS 地址，避免误请求其他目标。"""

    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    trusted_host = hostname == ALLOWED_SOURCE_DOMAIN or hostname.endswith(
        f".{ALLOWED_SOURCE_DOMAIN}"
    )
    if parsed.scheme.lower() != "https" or not trusted_host:
        raise SourceProbeError("Source Probe endpoint 必须是 CNEMC HTTPS 地址")
    if parsed.username or parsed.password:
        raise SourceProbeError("Source Probe endpoint 不得包含 URL 凭据")


def _redact_url(url: str) -> str:
    """移除 URL Query 和 Fragment，避免 Manifest 意外记录敏感参数。"""

    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def build_parser() -> argparse.ArgumentParser:
    """构造显式执行型 CLI；未提供 ``--execute`` 时不会发送请求。"""

    parser = argparse.ArgumentParser(
        description="对候选空气质量接口执行一次单城市 Source Probe。"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="明确允许本次命令发送一次网络请求。",
    )
    parser.add_argument("--city-code", choices=sorted(CITY_NAMES_BY_CODE))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--endpoint", default=CANDIDATE_API_URL)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行 CLI，并以非零状态报告任何请求、校验或落盘失败。"""

    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.execute:
        parser.print_help()
        print("\n未提供 --execute：未发送网络请求。", file=sys.stderr)
        return 2
    if not args.city_code:
        parser.error("--execute 必须同时提供 --city-code")

    try:
        result = run_probe(
            args.city_code,
            args.output_dir,
            endpoint=args.endpoint,
            timeout_seconds=args.timeout_seconds,
            max_response_bytes=args.max_response_bytes,
        )
    except SourceProbeError as exc:
        print(f"Source Probe 失败: {exc}", file=sys.stderr)
        return 1

    response_meta = result.manifest["response"]
    assert isinstance(response_meta, dict)
    print(
        json.dumps(
            {
                "batch_dir": str(result.batch_dir),
                "record_count": response_meta["record_count"],
                "sha256": response_meta["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
