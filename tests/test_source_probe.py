import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import parse_qs

from scripts.ingestion.source_probe import (
    CANDIDATE_API_URL,
    ProbeResponse,
    SourceProbeError,
    fetch_city_response,
    main,
    persist_snapshot,
    verify_snapshot,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_beijing_response.json"


class FakeHttpResponse:
    """提供 urllib 响应所需的最小测试替身。"""

    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        content_type: str = "application/json; charset=utf-8",
        url: str = CANDIDATE_API_URL,
    ) -> None:
        self._body = body
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]


class SourceProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_bytes = FIXTURE_PATH.read_bytes()

    def test_fetch_sends_one_whitelisted_city_request(self):
        captured = {}

        def fake_opener(request, *, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeHttpResponse(self.fixture_bytes)

        response = fetch_city_response(
            "110000",
            timeout_seconds=7,
            opener=fake_opener,
        )

        request = captured["request"]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(parse_qs(request.data.decode("ascii")), {"citycode": ["110000"]})
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(response.body, self.fixture_bytes)

    def test_persist_snapshot_writes_exact_bytes_and_manifest(self):
        response = ProbeResponse(
            status=200,
            content_type="application/json; charset=utf-8",
            body=self.fixture_bytes,
            final_url=CANDIDATE_API_URL,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = persist_snapshot(
                response,
                "110000",
                Path(temp_dir),
                requested_at=datetime(2026, 10, 16, 1, 2, 3, tzinfo=timezone.utc),
                batch_id="test-batch",
            )

            self.assertEqual(result.raw_path.read_bytes(), self.fixture_bytes)
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            expected_hash = hashlib.sha256(self.fixture_bytes).hexdigest()
            self.assertEqual(manifest["response"]["sha256"], expected_hash)
            self.assertEqual(manifest["response"]["record_count"], 1)
            self.assertEqual(manifest["city_name"], "北京")
            verify_snapshot(result.raw_path, expected_hash)

    def test_rejects_non_json_before_creating_output(self):
        response = ProbeResponse(
            status=200,
            content_type="text/html",
            body=b"<html>error</html>",
            final_url=CANDIDATE_API_URL,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "raw"
            with self.assertRaisesRegex(SourceProbeError, "Content-Type"):
                persist_snapshot(response, "110000", output_root)
            self.assertFalse(output_root.exists())

    def test_rejects_record_missing_required_field(self):
        payload = json.loads(self.fixture_bytes)
        del payload[0]["TimePoint"]
        response = ProbeResponse(
            status=200,
            content_type="application/json",
            body=json.dumps(payload).encode("utf-8"),
            final_url=CANDIDATE_API_URL,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(SourceProbeError, "TimePoint"):
                persist_snapshot(response, "110000", Path(temp_dir) / "raw")

    def test_rejects_oversized_response(self):
        def fake_opener(request, *, timeout):
            return FakeHttpResponse(b"123456")

        with self.assertRaisesRegex(SourceProbeError, "超过大小限制"):
            fetch_city_response(
                "110000",
                max_response_bytes=5,
                opener=fake_opener,
            )

    def test_rejects_untrusted_endpoint_before_request(self):
        request_sent = False

        def fake_opener(request, *, timeout):
            nonlocal request_sent
            request_sent = True
            return FakeHttpResponse(self.fixture_bytes)

        with self.assertRaisesRegex(SourceProbeError, "CNEMC HTTPS"):
            fetch_city_response(
                "110000",
                endpoint="http://127.0.0.1/internal",
                opener=fake_opener,
            )

        self.assertFalse(request_sent)

    def test_landing_failure_does_not_create_success_batch(self):
        response = ProbeResponse(
            status=200,
            content_type="application/json",
            body=self.fixture_bytes,
            final_url=CANDIDATE_API_URL,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            blocked_root = Path(temp_dir) / "blocked"
            blocked_root.write_text("not a directory", encoding="utf-8")

            with self.assertRaisesRegex(SourceProbeError, "落盘失败"):
                persist_snapshot(
                    response,
                    "110000",
                    blocked_root,
                    batch_id="failed-batch",
                )

            self.assertFalse((blocked_root / "failed-batch").exists())

    def test_verify_snapshot_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw.json"
            raw_path.write_bytes(self.fixture_bytes)

            with self.assertRaisesRegex(SourceProbeError, "SHA-256 不匹配"):
                verify_snapshot(raw_path, "0" * 64)

    def test_cli_without_execute_never_sends_request(self):
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main([])

        self.assertEqual(exit_code, 2)
        self.assertIn("未发送网络请求", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
