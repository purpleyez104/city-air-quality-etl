"""读取并校验 Raw Snapshot，返回 Canonical Record。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ingestion.response_normalizer import NormalizedAirQualityRecord, normalize_records
from scripts.ingestion.source_probe import SourceProbeError, verify_snapshot


def load_snapshot(batch_dir: Path) -> tuple[str, list[NormalizedAirQualityRecord]]:
    """验证 Manifest、Hash 与记录数后加载一个单城市批次。"""
    batch_dir = Path(batch_dir)
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    response = manifest.get("response", {})
    raw_path = batch_dir / response.get("raw_file", "")
    verify_snapshot(raw_path, response.get("sha256", ""))
    payload = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    records = normalize_records(payload)
    if len(records) != response.get("record_count"):
        raise SourceProbeError("Manifest record_count 与 Raw Snapshot 不一致")
    return str(manifest["batch_id"]), records
