import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.src.Api.services import chain_tasks
from app.src.Worker import chain

FAKE_PROBE = {
    "duration": 12.0,
    "fps": 25.0,
    "width": 1920,
    "height": 1080,
    "video_codec": "h264",
    "audio_codec": "aac",
    "has_video": True,
    "has_audio": True,
}


class FakeDb:
    def __init__(self, tasks):
        self.tasks = tasks
        self.params_writes = {}
        self.video_info_writes = {}
        self.status_writes = []

    def get_task(self, task_id):
        task = self.tasks.get(task_id)
        return dict(task) if task else None

    def update_task_params(self, task_id, params):
        self.params_writes[task_id] = params

    def update_task_video_info(self, task_id, video_info):
        self.video_info_writes[task_id] = video_info

    def update_task_status(self, task_id, status, progress=None, message=None):
        self.status_writes.append((task_id, status, message))
        self.tasks[task_id]["status"] = status


def make_task(task_id, category, status, step, next_id=None, result_path=None):
    return {
        "task_id": task_id,
        "task_category": category,
        "status": status,
        "progress": 100 if status == "COMPLETED" else 0,
        "chain_step": step,
        "chain_next_task_id": next_id,
        "result_path": result_path,
        "task_params": "{}",
    }


class ChainAdvanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        probe = patch("app.src.Utils.media_items.ffprobe_info", return_value=dict(FAKE_PROBE))
        probe.start()
        self.addCleanup(probe.stop)
        event = patch.object(chain, "send_event")
        self.send_event = event.start()
        self.addCleanup(event.stop)

    def _make_result(self, name="out.mp4"):
        path = self.tmp_dir / name
        path.write_bytes(b"0" * 2048)
        return path

    def test_completed_step_releases_next_step(self):
        result = self._make_result()
        fake = FakeDb(
            {
                "0001": make_task("0001", "convert", "COMPLETED", 0, "0002", str(result)),
                "0002": make_task("0002", "transcribe", "WAITING", 1),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.tasks["0002"]["status"], "PENDING")
        media_files = fake.params_writes["0002"]["media_files"]
        self.assertEqual(media_files[0]["upload_path"], str(result))
        self.assertEqual(fake.video_info_writes["0002"]["media_count"], 1)

    def test_enhance_step_gets_upscaler_fields(self):
        result = self._make_result("clip.mkv")
        fake = FakeDb(
            {
                "0001": make_task("0001", "convert", "COMPLETED", 0, "0002", str(result)),
                "0002": make_task("0002", "enhance", "WAITING", 1),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        params = fake.params_writes["0002"]
        self.assertEqual(params["upload_path"], str(result))
        self.assertEqual(params["filename"], "clip.mkv")
        self.assertEqual(params["input_type"], "Video")
        self.assertEqual(params["source_video_codec"], "h264")

    def test_zip_result_fails_next_step_instead_of_guessing(self):
        result = self._make_result("batch.zip")
        fake = FakeDb(
            {
                "0001": make_task("0001", "convert", "COMPLETED", 0, "0002", str(result)),
                "0002": make_task("0002", "enhance", "WAITING", 1),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.tasks["0002"]["status"], "FAILED")
        self.assertIn("压缩包", fake.status_writes[0][2])

    def test_subtitle_result_is_rejected_by_video_step(self):
        result = self._make_result("sub.srt")
        fake = FakeDb(
            {
                "0001": make_task("0001", "transcribe", "COMPLETED", 0, "0002", str(result)),
                "0002": make_task("0002", "enhance", "WAITING", 1),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.tasks["0002"]["status"], "FAILED")

    def test_failed_step_fails_every_waiting_step_downstream(self):
        fake = FakeDb(
            {
                "0001": make_task("0001", "convert", "FAILED", 0, "0002"),
                "0002": make_task("0002", "enhance", "WAITING", 1, "0003"),
                "0003": make_task("0003", "transcribe", "WAITING", 2),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.tasks["0002"]["status"], "FAILED")
        self.assertEqual(fake.tasks["0003"]["status"], "FAILED")
        self.assertEqual(self.send_event.call_count, 2)

    def test_advance_is_idempotent_for_already_released_step(self):
        result = self._make_result()
        fake = FakeDb(
            {
                "0001": make_task("0001", "convert", "COMPLETED", 0, "0002", str(result)),
                "0002": make_task("0002", "enhance", "PROCESSING", 1),
            }
        )
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.tasks["0002"]["status"], "PROCESSING")
        self.assertEqual(fake.params_writes, {})

    def test_plain_task_is_untouched(self):
        fake = FakeDb({"0001": make_task("0001", "enhance", "COMPLETED", None)})
        with patch.object(chain, "db", fake):
            chain.advance_chain("0001")

        self.assertEqual(fake.status_writes, [])


class ChainValidationTests(unittest.TestCase):
    def test_transcribe_must_be_last(self):
        steps = [{"category": "transcribe"}, {"category": "enhance"}]
        self.assertIn("最后一步", chain_tasks._validate_steps(steps))

    def test_multi_output_convert_mode_cannot_be_intermediate(self):
        steps = [
            {"category": "convert", "params": {"convert_mode": "export_frames"}},
            {"category": "enhance"},
        ]
        self.assertIn("多个文件", chain_tasks._validate_steps(steps))

    def test_multi_output_convert_mode_is_fine_as_last_step(self):
        steps = [
            {"category": "enhance"},
            {"category": "convert", "params": {"convert_mode": "export_frames"}},
        ]
        self.assertIsNone(chain_tasks._validate_steps(steps))

    def test_step_count_is_capped(self):
        steps = [{"category": "enhance"}] * (chain_tasks.CHAIN_MAX_STEPS + 1)
        self.assertIn("最多", chain_tasks._validate_steps(steps))

    def test_unknown_category_is_rejected(self):
        self.assertIn("不支持", chain_tasks._validate_steps([{"category": "download"}]))

    def test_empty_steps_rejected(self):
        self.assertIn("不能为空", chain_tasks._validate_steps([]))

    def test_composite_params_survive_form_parser(self):
        form = chain_tasks._as_form({"watermark_timeline": [{"text": "hi"}], "crf": 20, "fp16": True})
        self.assertEqual(form["watermark_timeline"], '[{"text": "hi"}]')
        self.assertEqual(form["crf"], 20)
        self.assertIs(form["fp16"], True)


if __name__ == "__main__":
    unittest.main()
