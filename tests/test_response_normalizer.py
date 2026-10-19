import copy
import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from scripts.ingestion.response_normalizer import (
    ResponseNormalizationError,
    normalize_records,
    parse_dotnet_business_date,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_beijing_response.json"


class ResponseNormalizerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]

    def test_parses_business_date_with_fixed_utc_plus_8(self):
        self.assertEqual(parse_dotnet_business_date("/Date(0)/"), date(1970, 1, 1))
        self.assertEqual(
            parse_dotnet_business_date("/Date(57600000+0800)/"),
            date(1970, 1, 2),
        )

    def test_normalizes_actual_shape_and_preserves_trace_fields(self):
        item = normalize_records([self.record])[0]

        self.assertEqual(item.source_id, 900001)
        self.assertEqual(item.city_code, "110000")
        self.assertEqual(item.city, "北京")
        self.assertEqual(item.source_area, "北京市")
        self.assertEqual(item.aqi, Decimal("52"))
        self.assertEqual(item.co, Decimal("0.6"))
        self.assertEqual(item.activity_advice, "建议适量减少户外活动")

    def test_sorts_unsorted_input_by_business_date(self):
        earlier = copy.deepcopy(self.record)
        earlier["Id"] = 900002
        earlier["TimePoint"] = "/Date(0)/"
        later = copy.deepcopy(self.record)
        later["Id"] = 900003
        later["TimePoint"] = "/Date(86400000)/"

        result = normalize_records([later, earlier])

        self.assertEqual([item.source_id for item in result], [900002, 900003])

    def test_allows_null_or_blank_numeric_value_as_missing(self):
        record = copy.deepcopy(self.record)
        record["AQI"] = None
        record["CO_24h"] = "  "

        item = normalize_records([record])[0]

        self.assertIsNone(item.aqi)
        self.assertIsNone(item.co)

    def test_rejects_invalid_or_non_finite_numeric_value(self):
        for invalid_value in (True, "not-a-number", "NaN", "Infinity"):
            with self.subTest(invalid_value=invalid_value):
                record = copy.deepcopy(self.record)
                record["AQI"] = invalid_value
                with self.assertRaisesRegex(ResponseNormalizationError, "AQI"):
                    normalize_records([record])

    def test_rejects_city_code_area_mismatch(self):
        record = copy.deepcopy(self.record)
        record["Area"] = "上海市"

        with self.assertRaisesRegex(ResponseNormalizationError, "不匹配"):
            normalize_records([record])

    def test_rejects_duplicate_source_id(self):
        duplicate = copy.deepcopy(self.record)
        duplicate["TimePoint"] = "/Date(86400000)/"

        with self.assertRaisesRegex(ResponseNormalizationError, "Id 重复"):
            normalize_records([self.record, duplicate])

    def test_rejects_duplicate_city_business_date(self):
        duplicate = copy.deepcopy(self.record)
        duplicate["Id"] = 900002

        with self.assertRaisesRegex(ResponseNormalizationError, "业务键重复"):
            normalize_records([self.record, duplicate])

    def test_rejects_invalid_date_without_partial_result(self):
        invalid = copy.deepcopy(self.record)
        invalid["Id"] = 900002
        invalid["TimePoint"] = "2026-01-02"

        with self.assertRaisesRegex(ResponseNormalizationError, "TimePoint 格式非法"):
            normalize_records([self.record, invalid])


if __name__ == "__main__":
    unittest.main()
