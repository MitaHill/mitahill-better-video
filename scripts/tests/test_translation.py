import json
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import requests

from app.src.Worker.pipelines.transcription.translation.providers import (
    OpenAICompatibleTranslator,
    TranslationFormatError,
    TranslationRequestError,
    TranslationServiceError,
)
from app.src.Worker.pipelines.transcription.translation.segments import _batches, translate_segments


def response(content, *, status=200, finish_reason="stop", headers=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = json.dumps({
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }).encode()
    result._content_consumed = True
    return result


def segments(count):
    return [{"start": i * 1.5, "end": i * 1.5 + 1, "text": f"line {i}"} for i in range(count)]


class TranslatorTests(unittest.TestCase):
    def translator(self, **kwargs):
        defaults = dict(base_url="http://localhost/v1", model="deepseek-flash", api_key="test",
                        prompt="Translate to {{target_language}}. Use a code block.")
        defaults.update(kwargs)
        translator = OpenAICompatibleTranslator(**defaults)
        self.addCleanup(translator.on_task_end)
        return translator

    def test_batch_size_and_utf8_limit_and_oversized_item(self):
        items = [{"id": i, "text": "中" * 1000} for i in range(5)]
        self.assertEqual([len(batch) for batch in _batches(items, 20)], [2, 2, 1])
        self.assertEqual([len(batch) for batch in _batches(items, 1)], [1] * 5)
        items[2]["text"] = "中" * 3000
        self.assertEqual([len(batch) for batch in _batches(items, 20)], [2, 1, 2])

    def test_batch_protocol_and_deepseek_parameters(self):
        translator = self.translator()
        session = Mock()
        session.post.return_value = response('{"translations":[{"id":2,"text":"你好"}]}')
        with patch.object(translator, "_session", return_value=session):
            result = translator.translate_batch([{"id": 2, "text": "hello"}], "zh", context_before=["before"])
        self.assertEqual(result, {2: "你好"})
        sent = session.post.call_args.kwargs
        self.assertEqual(sent["timeout"], (10, 90))
        self.assertEqual(sent["json"]["thinking"], {"type": "disabled"})
        self.assertEqual(sent["json"]["max_tokens"], 8192)
        self.assertIn("overrides", sent["json"]["messages"][0]["content"])
        data = json.loads(sent["json"]["messages"][1]["content"])
        self.assertEqual(data["context_before"], ["before"])
        self.assertEqual(translator.stats["total_tokens"], 20)

    def test_other_models_do_not_receive_thinking_parameter(self):
        translator = self.translator(model="other-model")
        session = Mock()
        session.post.return_value = response("```你好```")
        with patch.object(translator, "_session", return_value=session):
            self.assertEqual(translator.translate_text("hello", "zh"), "你好")
        self.assertNotIn("thinking", session.post.call_args.kwargs["json"])

    def test_missing_duplicate_unknown_boolean_or_empty_ids_are_rejected(self):
        translator = self.translator()
        cases = [[], [{"id": 0, "text": "a"}, {"id": 0, "text": "b"}],
                 [{"id": 9, "text": "a"}], [{"id": False, "text": "a"}],
                 [{"id": 0, "text": " "}], [{"id": "0", "text": "a"}]]
        for rows in cases:
            with self.subTest(rows=rows), patch.object(translator, "_request", return_value={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"translations": rows})}}],
            }):
                with self.assertRaises(TranslationFormatError):
                    translator.translate_batch([{"id": 0, "text": "a"}], "zh")

    def test_truncated_output_is_rejected_before_parsing(self):
        translator = self.translator()
        data = response('{"translations":[{"id":0,"text":"a"}]}', finish_reason="length").json()
        with patch.object(translator, "_request", return_value=data):
            with self.assertRaises(TranslationFormatError):
                translator.translate_batch([{"id": 0, "text": "a"}], "zh")

    def test_retry_transient_errors_and_release_responses(self):
        for failure in (requests.ReadTimeout(), requests.ConnectionError(), response("", status=500),
                        response("", status=429, headers={"Retry-After": "99"})):
            translator = self.translator()
            session = Mock()
            session.post.side_effect = [failure, response("```ok```")]
            with self.subTest(failure=type(failure).__name__), patch.object(translator, "_session", return_value=session), \
                    patch("app.src.Worker.pipelines.transcription.translation.providers.time.sleep") as sleep:
                self.assertEqual(translator.translate_text("hello", "zh"), "ok")
                self.assertEqual(translator.stats["requests"], 2)
                self.assertEqual(translator.stats["retries"], 1)
                self.assertEqual(sleep.call_args.args[0], 30 if isinstance(failure, requests.Response) and failure.status_code == 429 else 1)

    def test_retry_after_http_date(self):
        deadline = datetime.now(timezone.utc) + timedelta(seconds=15)
        result = response("", headers={"Retry-After": format_datetime(deadline)})
        self.assertGreater(OpenAICompatibleTranslator._retry_delay(result, 0), 10)
        self.assertLessEqual(OpenAICompatibleTranslator._retry_delay(result, 0), 15)

    def test_retry_budget_is_three_requests(self):
        translator = self.translator()
        session = Mock()
        session.post.side_effect = requests.ReadTimeout("secret response")
        with patch.object(translator, "_session", return_value=session), \
                patch("app.src.Worker.pipelines.transcription.translation.providers.time.sleep") as sleep:
            with self.assertRaises(TranslationRequestError) as caught:
                translator.translate_text("hello", "zh")
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(session.post.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_auth_and_missing_endpoint_fail_without_fallback(self):
        for status in (401, 403, 404):
            translator = self.translator()
            session = Mock()
            session.post.return_value = response("secret response", status=status)
            with self.subTest(status=status), patch.object(translator, "_session", return_value=session), \
                    patch("app.src.Worker.pipelines.transcription.translation.providers.time.sleep") as sleep:
                with self.assertRaises(TranslationServiceError):
                    translate_segments(segments(2), translator, "zh")
                self.assertEqual(session.post.call_count, 1)
                self.assertEqual(translator.stats["fallbacks"], 0)
                sleep.assert_not_called()

    def test_bad_batch_only_retries_its_own_items(self):
        translator = self.translator(batch_size=2, concurrency=1)
        def batch(items, *args, **kwargs):
            if items[0]["id"] == 0:
                raise TranslationFormatError("bad JSON")
            return {item["id"]: "译" + item["text"] for item in items}
        with patch.object(translator, "translate_batch", side_effect=batch), \
                patch.object(translator, "translate_text", side_effect=lambda text, *a: "译" + text) as single:
            result = translate_segments(segments(4), translator, "zh")
        self.assertEqual(single.call_count, 2)
        self.assertEqual([row["text"] for row in result], ["译line 0", "译line 1", "译line 2", "译line 3"])

    def test_exhausted_batch_does_not_disable_remaining_translation(self):
        translator = self.translator(batch_size=1, concurrency=1)
        with patch.object(translator, "translate_batch", side_effect=[
            TranslationRequestError("timeout"), {1: "译line 1"},
        ]):
            result = translate_segments(segments(2), translator, "zh")
        self.assertEqual([row["text"] for row in result], ["line 0", "译line 1"])
        self.assertEqual(translator.stats["fallbacks"], 1)

    def test_single_fallback_never_uses_raw_batch_json(self):
        for mode, expected in (("source_text", "line 0"), ("model_full_text", "single raw")):
            translator = self.translator(fallback_mode=mode)
            session = Mock()
            session.post.side_effect = [response("batch raw must never appear"), response("single raw")]
            with patch.object(translator, "_session", return_value=session):
                result = translate_segments(segments(1), translator, "zh")
            self.assertEqual(result[0]["text"], expected)
            self.assertEqual(translator.stats["fallbacks"], 1)

    def test_empty_items_and_neighbor_context_are_preserved(self):
        translator = self.translator(batch_size=1, concurrency=1)
        source = segments(5)
        source[1]["text"] = "  "
        calls = []
        def batch(items, *args, **kwargs):
            calls.append((items, kwargs))
            return {item["id"]: "译" + item["text"] for item in items}
        with patch.object(translator, "translate_batch", side_effect=batch):
            result = translate_segments(source, translator, "zh")
        self.assertEqual([items[0]["id"] for items, _ in calls], [0, 2, 3, 4])
        self.assertEqual(calls[1][1]["context_before"], ["line 0"])
        self.assertEqual(calls[1][1]["context_after"], ["line 3", "line 4"])
        self.assertEqual(result[1]["text"], "")
        self.assertEqual(source[1]["text"], "  ")
        for original, translated in zip(source, result):
            self.assertEqual(original["start"], translated["start"])
            self.assertEqual(original["end"], translated["end"])

    def test_all_empty_and_disabled_translation(self):
        translator = self.translator()
        callback = Mock()
        self.assertEqual(translate_segments([{"text": " "}], translator, "zh", callback), [{"text": ""}])
        callback.assert_called_once_with(1, 1)
        self.assertEqual(translate_segments([{"text": "original"}], None, "zh"), [{"text": "original"}])

    def test_single_failure_is_counted_and_other_items_continue(self):
        translator = self.translator()
        with patch.object(translator, "translate_batch", side_effect=TranslationFormatError()), \
                patch.object(translator, "translate_text", side_effect=[TranslationRequestError(), "译line 1"]):
            result = translate_segments(segments(2), translator, "zh")
        self.assertEqual([row["text"] for row in result], ["line 0", "译line 1"])
        self.assertEqual(translator.stats["fallbacks"], 1)

    def test_connections_are_closed_on_task_end(self):
        translator = self.translator()
        with patch("app.src.Worker.pipelines.transcription.translation.providers.requests.Session") as factory:
            session = translator._session()
            self.assertIs(session, translator._session())
            factory.assert_called_once()
        translator.on_task_end()
        session.close.assert_called_once()

    def test_progress_is_throttled_and_final_update_is_forced(self):
        translator = self.translator(batch_size=1, concurrency=1)
        updates = []
        clock = Mock()
        clock.monotonic.side_effect = [0, 0.4, 1.1, 1.5, 2.2, 2.4, 3.4, 3.5]
        def batch(items, *args, **kwargs):
            return {item["id"]: "译" + item["text"] for item in items}
        with patch.object(translator, "translate_batch", side_effect=batch), \
                patch("app.src.Worker.pipelines.transcription.translation.segments.time", clock):
            translate_segments(segments(6), translator, "zh", lambda done, total: updates.append((done, total)))
        self.assertEqual(updates, [(2, 6), (4, 6), (6, 6)])

    def test_translation_progress_does_not_probe_gpu(self):
        from app.src.Worker.pipelines.transcription import progress
        with patch.object(progress.db, "update_task_status"), patch.object(progress, "send_event") as event, \
                patch.object(progress, "get_gpu_utilization") as gpu:
            progress.emit_progress("test", 80, "翻译中", stage="translate")
        gpu.assert_not_called()
        self.assertIsNone(event.call_args.args[0]["gpu_util"])

    def test_batch_options_come_from_environment_config_not_task_input(self):
        from app.src.Worker.pipelines.transcription import options
        with patch.object(options.config, "TRANSCRIPTION_TRANSLATOR_BATCH_SIZE", 12), \
                patch.object(options.config, "TRANSCRIPTION_TRANSLATOR_CONCURRENCY", 3):
            result = options.normalize_transcription_options({
                "translator_batch_size": 50, "translator_concurrency": 16,
            })
        self.assertEqual(result["translator_batch_size"], 12)
        self.assertEqual(result["translator_concurrency"], 3)


class HTTPTranslationTests(unittest.TestCase):
    def test_600_segments_bounded_concurrency_order_and_connection_reuse(self):
        lock = threading.Lock()
        state = {"active": 0, "peak": 0, "requests": 0, "ports": set(), "completion": []}
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args):
                pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                items = json.loads(data["messages"][-1]["content"])["items"]
                first = items[0]["id"]
                with lock:
                    state["active"] += 1
                    state["requests"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                    state["ports"].add(self.client_address[1])
                time.sleep(0.15 if first == 0 else 0.02)
                content = json.dumps({"translations": [{"id": item["id"], "text": "译" + item["text"]} for item in reversed(items)]})
                body = response(content).content
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
                with lock:
                    state["active"] -= 1
                    state["completion"].append(first)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        translator = OpenAICompatibleTranslator(base_url=f"http://127.0.0.1:{server.server_port}/v1",
                                                model="deepseek-flash", api_key="", prompt="Translate to {{target_language}}.")
        source = segments(600)
        updates = []
        main_thread = threading.get_ident()
        def progress(done, total):
            self.assertEqual(threading.get_ident(), main_thread)
            updates.append((done, total, time.monotonic()))
        try:
            result = translate_segments(source, translator, "zh", progress)
        finally:
            translator.on_task_end()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(state["requests"], 30)
        self.assertGreater(state["peak"], 1)
        self.assertLessEqual(state["peak"], 4)
        self.assertLessEqual(len(state["ports"]), 4)
        self.assertNotEqual(state["completion"][0], 0)
        self.assertEqual([row["text"] for row in result], ["译" + row["text"] for row in source])
        self.assertEqual([(row["start"], row["end"]) for row in result], [(row["start"], row["end"]) for row in source])
        self.assertEqual(updates[-1][:2], (600, 600))
        self.assertEqual([row[0] for row in updates], sorted(set(row[0] for row in updates)))
        for previous, current in zip(updates[:-2], updates[1:-1]):
            self.assertGreaterEqual(current[2] - previous[2], 1)
        self.assertEqual(translator.stats["fallbacks"], 0)


if __name__ == "__main__":
    unittest.main()
