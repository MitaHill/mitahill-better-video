from app.src.Api.services.admin.transcription_config import get_elevenlabs_api_key

from .scribe_engine import ScribeEngine
from .whisper_engine import ENGINE as WHISPER_ENGINE


class TranscriptionEngine:
    def __init__(self, whisper_engine=None, scribe_engine=None):
        self.whisper = whisper_engine or WHISPER_ENGINE
        self.scribe = scribe_engine or ScribeEngine()

    def transcribe(self, media_path, *, options, progress_callback=None):
        backend = str(options.get("transcription_backend") or "whisper").strip().lower()
        if backend == "elevenlabs":
            # 密钥始终在任务进程内读取，不进入任务参数
            return self.scribe.transcribe(
                media_path,
                api_key=get_elevenlabs_api_key(),
                language=options.get("language", "auto"),
                max_line_chars=options.get("max_line_chars", 42),
                progress_callback=progress_callback,
            )
        if backend != "whisper":
            raise RuntimeError(f"不支持的转录引擎: {backend}")

        def on_whisper_progress(done, total):
            if not progress_callback or total <= 0:
                return
            progress_callback(
                {
                    "ratio": min(float(done), float(total)) / float(total),
                    "stage": "transcribe",
                    "message": f"语音识别中 {done:.1f}/{total:.1f} 秒",
                    "unit_done": done,
                    "unit_total": total,
                    "unit_label": "音频秒",
                }
            )

        return self.whisper.transcribe(
            media_path,
            backend="whisper",
            model_name=options.get("whisper_model", "large-v3"),
            language=options.get("language", "auto"),
            temperature=options.get("temperature", 0.0),
            beam_size=options.get("beam_size", 5),
            best_of=options.get("best_of", 5),
            progress_callback=on_whisper_progress,
        )

    def finalize_task(self):
        self.whisper.finalize_task()
        self.scribe.finalize_task()


ENGINE = TranscriptionEngine()
