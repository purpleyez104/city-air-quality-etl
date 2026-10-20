import json
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from scripts.ingestion.response_normalizer import normalize_records
from scripts.pipeline import run_etl
from scripts.processing.quality import clean_record


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_beijing_response.json"


class FakeRepository:
    """保留 Raw、Clean 与质量键的最小内存 Repository。"""

    def __init__(self, rows, clean=()):
        self.rows = rows
        self.clean = {(item.city, item.business_date): item for item in clean}
        self.issues = {}
        self.runs = []

    def start_run(self, run_id, batch_id):
        self.current_run = {"run_id": run_id, "batch_id": batch_id}

    def fetch_raw(self, batch_id=None):
        return list(self.rows)

    def fetch_clean_lineage(self):
        return {
            key: item.source_raw_id
            for key, item in self.clean.items()
        }

    def upsert_clean(self, run_id, records):
        items = list(records)
        for item in items:
            self.clean[(item.city, item.business_date)] = item
        return len(items)

    def upsert_issues(self, run_id, issues):
        items = list(issues)
        for item in items:
            self.issues[item.issue_key] = item
        return len(items)

    def finish_run(self, run_id, input_count, output_count, issue_count):
        self.runs.append((input_count, output_count, issue_count, "success"))

    def fail_run(self, run_id, message):
        self.runs.append((0, 0, 0, f"failed:{message}"))


def raw_row(raw_id, record):
    row = asdict(record)
    row["raw_id"] = raw_id
    return row


class PipelineTest(unittest.TestCase):
    def test_overlap_keeps_both_raw_and_upserts_one_api_clean_record(self):
        source = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]
        api = replace(
            normalize_records([source])[0],
            source_id=1,
            source_record_key="cnemc_api:110000:1",
        )
        history = replace(
            api,
            source_id=999_999_999,
            source_type="quotsoft_history_csv",
            source_record_key="quotsoft_history_csv:110000:2026-01-01",
            source_time_point="2026-01-01T23:00:00+08:00",
            observation_hour=23,
        )
        history_clean, _ = clean_record(10, history)
        repository = FakeRepository(
            [raw_row(10, history), raw_row(11, api)],
            clean=[history_clean],
        )

        first = run_etl(repository, "overlap-fixture")
        second = run_etl(repository, "overlap-fixture")

        self.assertEqual(len(repository.rows), 2)
        self.assertEqual(len(repository.clean), 1)
        self.assertEqual(next(iter(repository.clean.values())).source_raw_id, 11)
        self.assertEqual(len(repository.issues), 1)
        self.assertEqual(first["input_count"], 2)
        self.assertEqual(first["overlap_key_count"], 1)
        self.assertEqual(first["changed_source_count"], 1)
        self.assertEqual(second["output_count"], 1)
        self.assertEqual(second["overlap_key_count"], 1)
        self.assertEqual(second["unchanged_source_count"], 1)
        self.assertEqual(len(repository.runs), 2)


if __name__ == "__main__":
    unittest.main()
