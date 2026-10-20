import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.reporting.dashboard import generate_dashboard


class DashboardTest(unittest.TestCase):
    def test_generates_expected_artifacts(self):
        clean = [
            {
                "city": "北京", "business_date": date(2025, 12, 31), "aqi": 52,
                "pm10": 40, "pm2_5": 21, "so2": 4, "co": 0.6, "no2": 18,
                "o3": 90, "has_missing": False,
                "source_type": "quotsoft_history_csv",
            },
            {
                "city": "北京", "business_date": date(2026, 10, 16), "aqi": None,
                "pm10": 42, "pm2_5": None, "so2": 5, "co": 0.7, "no2": 20,
                "o3": 88, "has_missing": True,
                "source_type": "cnemc_api",
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = generate_dashboard(clean, [], Path(temp_dir))
            self.assertTrue(paths["dashboard.html"].exists())
            self.assertIn("空气质量 ETL Dashboard", paths["dashboard.html"].read_text(encoding="utf-8"))
            self.assertTrue(paths["city_summary.csv"].exists())
            self.assertTrue(paths["monthly_summary.csv"].exists())
            report = paths["report.md"].read_text(encoding="utf-8")
            self.assertIn("缺失值未填充", report)
            self.assertIn("2025 历史 CSV：1", report)
            self.assertIn("2026 API：1", report)

    def test_rejects_empty_clean_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "没有"):
                generate_dashboard([], [], Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
