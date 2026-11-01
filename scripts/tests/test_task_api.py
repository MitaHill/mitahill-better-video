import io
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from app.src.Api.routes import tasks, transcriptions
from app.src.Api.routes.transcriptions_handlers import submission


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(tasks, "OUTPUT_ROOT", self.root))
        self.stack.enter_context(patch.object(tasks, "resolve_request_client_ip", return_value="127.0.0.1"))
        self.stack.enter_context(patch.object(transcriptions, "resolve_request_client_ip", return_value="127.0.0.1"))
        self.get_task = self.stack.enter_context(patch.object(tasks.db, "get_task"))
        self.stack.enter_context(patch.object(tasks.db, "get_task_progress", return_value=[]))
        self.stack.enter_context(patch.object(tasks.db, "get_latest_segment_progress", return_value=[]))
        self.stack.enter_context(patch.object(tasks.db_gpu, "get_current_gpu_usage", return_value={}))
        app = Flask(__name__)
        app.testing = True
        app.register_blueprint(tasks.bp)
        app.register_blueprint(transcriptions.bp)
        self.client = app.test_client()

    def task(self, status="COMPLETED", result_path=None, params=None):
        return {
            "task_id": "0123",
            "status": status,
            "progress": 100 if status == "COMPLETED" else 0,
            "message": "测试任务",
            "task_params": json.dumps(params or {"task_category": "enhance"}),
            "video_info": "{}",
            "created_at": "2026-11-01 00:00:00",
            "updated_at": "2026-11-01 00:00:01",
            "result_path": str(result_path) if result_path else None,
        }

    def test_submit_enhancement_returns_relative_status_url(self):
        with patch.object(tasks, "create_enhance_task", return_value=("0123", None)) as create:
            response = self.client.post("/api/tasks", data={"file": (io.BytesIO(b"video"), "input.mp4")})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json, {"task_id": "0123", "status_url": "/api/tasks/0123"})
        self.assertEqual(create.call_args.args[1]["task_category"], "enhance")

    def test_enhancement_submission_errors_remain_compatible(self):
        response = self.client.post("/api/tasks")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "file is required"})
        with patch.object(tasks, "create_enhance_task", return_value=("0123", "unsupported codec")):
            response = self.client.post("/api/tasks", data={"file": (io.BytesIO(b"bad"), "input.mp4")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"task_id": "0123", "error": "unsupported codec"})

    def test_submit_transcription_single_and_batch(self):
        with ExitStack() as stack:
            stack.enter_context(patch.object(submission, "apply_transcription_form_params", return_value=({}, None)))
            stack.enter_context(patch.object(submission, "validate_transcription_backend_guard", return_value=None))
            stack.enter_context(patch.object(submission, "validate_translation_provider_guard", return_value=None))
            create = stack.enter_context(patch.object(submission, "create_transcription_tasks"))
            create.return_value = (None, ["0123"], [])
            response = self.client.post("/api/transcriptions", data={"file": (io.BytesIO(b"audio"), "input.wav")})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json, {
                "task_id": "0123", "task_ids": ["0123"], "status_url": "/api/tasks/0123",
            })
            create.return_value = ("9500", ["0123", "0124"], [])
            response = self.client.post("/api/transcriptions", data={
                "media_files": [(io.BytesIO(b"a"), "a.wav"), (io.BytesIO(b"b"), "b.wav")],
            })
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json, {"task_id": "0123", "task_ids": ["0123", "0124"], "batch_id": "9500"})

    def test_unknown_task_query_and_download(self):
        self.get_task.return_value = None
        for endpoint in ("/api/tasks/0123", "/api/tasks/0123/result"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json["error_code"], "task_not_found")

    def test_unfinished_and_failed_tasks_never_offer_result(self):
        result = self.root / "partial.mp4"
        result.write_bytes(b"partial")
        for status in ("PENDING", "PROCESSING", "WAITING", "FAILED"):
            with self.subTest(status=status):
                self.get_task.side_effect = lambda _: self.task(status, result)
                response = self.client.get("/api/tasks/0123")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["status"], status)
                self.assertFalse(response.json["result_available"])
                self.assertIsNone(response.json["result_url"])
                response = self.client.get("/api/tasks/0123/result")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json["error_code"], "result_not_ready")
                self.assertEqual(response.json["status"], status)

    def assert_downloadable(self, task, expected):
        self.get_task.side_effect = lambda _: dict(task)
        response = self.client.get("/api/tasks/0123")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["result_available"])
        self.assertEqual(response.json["result_url"], "/api/tasks/0123/result")
        self.assertEqual(response.json["created_at"], "2026-11-01T00:00:00+00:00")
        self.assertIsInstance(response.json["task_params"], dict)
        with self.client.get(response.json["result_url"]) as download:
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.data, expected.read_bytes())
            self.assertIn("attachment", download.headers["Content-Disposition"])
            self.assertIn(expected.name, download.headers["Content-Disposition"])

    def test_completed_result_and_secret_masking(self):
        result = self.root / "enhanced.mp4"
        result.write_bytes(b"enhanced video")
        task = self.task(result_path=result, params={"task_category": "enhance", "translator_api_key": "secret"})
        self.assert_downloadable(task, result)
        self.assertEqual(self.client.get("/api/tasks/0123").json["task_params"]["translator_api_key"], "********")

    def test_legacy_result_lookup_matches_download(self):
        result = self.root / "sr_input.mp4"
        result.write_bytes(b"legacy output")
        self.assert_downloadable(self.task(params={"filename": "input.mp4"}), result)

    def test_subtitle_zip_lookup_matches_download(self):
        result = self.root / "run_0123" / "results" / "subtitles.zip"
        result.parent.mkdir(parents=True)
        result.write_bytes(b"subtitle archive")
        self.assert_downloadable(self.task(params={"task_category": "transcribe"}), result)

    def test_missing_or_directory_result_is_unavailable(self):
        directory = self.root / "not_a_file.mp4"
        directory.mkdir()
        for path in (self.root / "missing.mp4", directory):
            with self.subTest(path=path):
                self.get_task.side_effect = lambda _: self.task(result_path=path)
                response = self.client.get("/api/tasks/0123")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json["result_available"])
                self.assertIsNone(response.json["result_url"])
                response = self.client.get("/api/tasks/0123/result")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json["error_code"], "result_missing")


if __name__ == "__main__":
    unittest.main()
