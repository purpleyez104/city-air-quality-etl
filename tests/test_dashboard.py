import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.reporting.dashboard import generate_dashboard


class DashboardTest(unittest.TestCase):
    def test_generates_expected_artifacts(self):
        clean = [{
            "city": "北京", "business_date": date(2026, 10, 16), "aqi": 52,
            "pm10": 40, "pm2_5": 21, "so2": 4, "co": 0.6, "no2": 18,
            "o3": 90, "has_missing": False,
        }]
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = generate_dashboard(clean, [], Path(temp_dir))
            self.assertTrue(paths["dashboard.html"].exists())
            self.assertIn("空气质量 ETL Dashboard", paths["dashboard.html"].read_text(encoding="utf-8"))
            self.assertTrue(paths["city_summary.csv"].exists())

    def test_rejects_empty_clean_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "没有"):
                generate_dashboard([], [], Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
