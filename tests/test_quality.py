import copy
import json
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts.ingestion.response_normalizer import normalize_records
from scripts.processing.quality import clean_record, deduplicate_records


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_beijing_response.json"


class QualityTest(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]

    def test_valid_record_has_no_issue(self):
        clean, issues = clean_record(7, normalize_records([self.source])[0])
        self.assertEqual(clean.source_raw_id, 7)
        self.assertFalse(clean.has_missing)
        self.assertEqual(issues, [])

    def test_missing_value_is_preserved_and_tracked(self):
        source = copy.deepcopy(self.source)
        source["PM2_5_24h"] = None
        clean, issues = clean_record(8, normalize_records([source])[0])
        self.assertIsNone(clean.pm2_5)
        self.assertTrue(clean.has_missing)
        self.assertEqual(issues[0].issue_code, "MISSING")

    def test_out_of_range_value_becomes_null_and_is_tracked(self):
        source = copy.deepcopy(self.source)
        source["AQI"] = Decimal("501")
        clean, issues = clean_record(9, normalize_records([source])[0])
        self.assertIsNone(clean.aqi)
        self.assertEqual(issues[0].issue_code, "OUT_OF_RANGE")
        self.assertEqual(issues[0].original_value, "501")

    def test_issue_key_is_stable_across_runs(self):
        source = copy.deepcopy(self.source)
        source["CO_24h"] = None
        record = normalize_records([source])[0]
        first = clean_record(1, record)[1][0]
        second = clean_record(2, record)[1][0]
        self.assertEqual(first.issue_key, second.issue_key)

    def test_duplicate_business_key_is_deterministic_within_same_source(self):
        first = normalize_records([self.source])[0]
        duplicate_source = copy.deepcopy(self.source)
        duplicate_source["Id"] = first.source_id + 1
        second = normalize_records([duplicate_source])[0]

        selected, issues = deduplicate_records([(1, first), (2, second)])

        self.assertEqual(selected[0][1].source_id, second.source_id)
        self.assertEqual(issues[0].issue_code, "DUPLICATE")

    def test_api_wins_history_overlap_regardless_of_source_id_and_input_order(self):
        api = replace(
            normalize_records([self.source])[0],
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

        first, _ = deduplicate_records([(10, history), (11, api)])
        reversed_result, _ = deduplicate_records([(11, api), (10, history)])

        self.assertEqual(first[0][1].source_type, "cnemc_api")
        self.assertEqual(reversed_result[0][1].source_type, "cnemc_api")

    def test_rejects_unregistered_source_type(self):
        record = replace(
            normalize_records([self.source])[0],
            source_type="unknown_source",
            business_date=date(2026, 1, 1),
        )

        with self.assertRaisesRegex(ValueError, "source_type"):
            deduplicate_records([(1, record)])


if __name__ == "__main__":
    unittest.main()
