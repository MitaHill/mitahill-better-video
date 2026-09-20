import unittest
from unittest.mock import patch

from app.src.Worker import loop


class FakeProcess:
    def __init__(self, returncode=None):
        self.pid = 4321
        self.returncode = returncode
        self.wait_calls = 0

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_calls += 1
        self.returncode = 0
        return self.returncode


class TaskProcessSupervisorTests(unittest.TestCase):
    def setUp(self):
        loop._active_process = None

    def test_completed_task_waits_for_its_own_cleanup(self):
        process = FakeProcess()
        with patch.object(loop.subprocess, "Popen", return_value=process), patch.object(
            loop.db, "get_task", return_value={"status": "COMPLETED"}
        ), patch.object(loop.os, "killpg") as killpg:
            loop._run_task_process("0001")

        self.assertEqual(process.wait_calls, 1)
        killpg.assert_not_called()

    def test_failed_task_process_group_is_stopped(self):
        process = FakeProcess()
        with patch.object(loop.subprocess, "Popen", return_value=process), patch.object(
            loop.db, "get_task", return_value={"status": "FAILED"}
        ), patch.object(loop.os, "killpg") as killpg:
            loop._run_task_process("0001")

        killpg.assert_called_once_with(process.pid, loop.signal.SIGKILL)

    def test_unexpected_exit_marks_task_failed(self):
        process = FakeProcess(returncode=7)
        task = {"status": "PROCESSING", "progress": 42, "task_category": "enhance"}
        with patch.object(loop.subprocess, "Popen", return_value=process), patch.object(
            loop.db, "get_task", return_value=task
        ), patch.object(loop.db, "update_task_status") as update_status, patch.object(loop, "send_event") as send_event:
            loop._run_task_process("0001")

        update_status.assert_called_once_with(
            "0001", "FAILED", progress=42, message="Task process exited unexpectedly (code 7)."
        )
        self.assertEqual(send_event.call_args.args[0]["status"], "FAILED")

    def test_start_failure_marks_task_failed(self):
        task = {"status": "PROCESSING", "progress": 0, "task_category": "enhance"}
        with patch.object(loop.subprocess, "Popen", side_effect=OSError("permission denied")), patch.object(
            loop.db, "get_task", return_value=task
        ), patch.object(loop.db, "update_task_status") as update_status, patch.object(loop, "send_event"):
            loop._run_task_process("0001")

        self.assertEqual(update_status.call_args.args[:2], ("0001", "FAILED"))
        self.assertIn("Failed to start task process", update_status.call_args.kwargs["message"])

if __name__ == "__main__":
    unittest.main()
