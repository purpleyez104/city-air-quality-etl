import tempfile
import unittest
from pathlib import Path

from scripts.ingestion.history_csv_loader import HistoryCsvError, load_history_csv


HEADER = "date,hour,type,北京,上海,广州,成都,武汉\n"
TYPES = (
    "AQI",
    "PM10_24h",
    "PM2.5_24h",
    "SO2_24h",
    "CO_24h",
    "NO2_24h",
    "O3_8h_24h",
)


def write_day(
    root: Path,
    day: str,
    *,
    hours: tuple[int, ...] = (23,),
    blank_type: str | None = None,
) -> Path:
    """写入满足真实数据横向结构的最小测试文件。"""

    lines = [HEADER]
    for hour in hours:
        for index, metric_type in enumerate(TYPES, start=1):
            values = [str(index + offset) for offset in range(5)]
            if metric_type == blank_type:
                values[0] = ""
            lines.append(f"{day},{hour},{metric_type},{','.join(values)}\n")
    path = root / f"china_cities_{day}.csv"
    path.write_text("".join(lines), encoding="utf-8-sig")
    return path


class HistoryCsvLoaderTest(unittest.TestCase):
    def test_builds_five_daily_records_at_target_hour(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_day(root, "20250101", hours=(22, 23))

            result = load_history_csv(root)

            self.assertEqual(result.file_count, 1)
            self.assertEqual(len(result.records), 5)
            self.assertEqual(result.fallback_count, 0)
            self.assertEqual({item.observation_hour for item in result.records}, {23})
            self.assertEqual(
                result.records[0].source_record_key,
                "quotsoft_history_csv:110000:2025-01-01",
            )

    def test_falls_back_only_when_target_hour_is_absent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_day(root, "20250102", hours=(20, 22))

            result = load_history_csv(root)

            self.assertEqual(result.fallback_count, 5)
            self.assertEqual({item.observation_hour for item in result.records}, {22})

    def test_preserves_blank_value_without_cross_hour_fill(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_day(root, "20250103", hours=(22, 23), blank_type="PM2.5_24h")

            result = load_history_csv(root)
            beijing = next(item for item in result.records if item.city == "北京")

            self.assertIsNone(beijing.pm2_5)
            self.assertEqual(beijing.observation_hour, 23)
            self.assertEqual(result.missing_value_count, 1)

    def test_rejects_filename_and_row_date_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_day(root, "20250104")
            content = path.read_text(encoding="utf-8-sig").replace(
                "20250104,", "20250105,", 1
            )
            path.write_text(content, encoding="utf-8-sig")

            with self.assertRaisesRegex(HistoryCsvError, "日期"):
                load_history_csv(root)


if __name__ == "__main__":
    unittest.main()
