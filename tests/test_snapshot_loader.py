import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.ingestion.snapshot_loader import load_snapshot
from scripts.ingestion.source_probe import CANDIDATE_API_URL, ProbeResponse, persist_snapshot


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_beijing_response.json"


class SnapshotLoaderTest(unittest.TestCase):
    def test_loads_verified_snapshot(self):
        response = ProbeResponse(
            status=200, content_type="application/json",
            body=FIXTURE_PATH.read_bytes(), final_url=CANDIDATE_API_URL,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = persist_snapshot(
                response, "110000", Path(temp_dir), batch_id="fixture-batch",
                requested_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
            )
            batch_id, records = load_snapshot(result.batch_dir)
            self.assertEqual(batch_id, "fixture-batch")
            self.assertEqual(len(records), 1)

    def test_rejects_tampered_raw_file(self):
        response = ProbeResponse(
            status=200, content_type="application/json",
            body=FIXTURE_PATH.read_bytes(), final_url=CANDIDATE_API_URL,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result = persist_snapshot(response, "110000", Path(temp_dir), batch_id="tampered")
            result.raw_path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(Exception, "SHA-256"):
                load_snapshot(result.batch_dir)


if __name__ == "__main__":
    unittest.main()
