from .common import DB_PATH, get_connection, logger
from .control import clear_task_cancel_request, is_task_cancel_requested, request_task_cancel
from .progress import (
    get_latest_segment_progress,
    get_segment_progress,
    get_task_progress,
    update_segment_progress,
    upsert_segment,
    upsert_task_progress,
)
from .schema import init_db
from .streams import append_task_stream_event, list_task_stream_events
from .tasks import (
    cleanup_old_tasks,
    count_processing_tasks,
    create_task,
    delete_task,
    get_next_task_atomic,
    get_task,
    get_unfinished_tasks,
    mark_stuck_tasks,
    update_task_result,
    update_task_status,
    update_task_video_info,
)
from .transcription_state import (
    clear_transcription_translation_segments,
    get_transcription_media_state,
    get_transcription_translation_segment,
    list_transcription_translation_segments,
    upsert_transcription_media_state,
    upsert_transcription_translation_segment,
)

__all__ = [
    "DB_PATH",
    "logger",
    "init_db",
    "get_connection",
    "create_task",
    "get_task",
    "update_task_status",
    "update_task_result",
    "update_task_video_info",
    "delete_task",
    "get_next_task_atomic",
    "cleanup_old_tasks",
    "mark_stuck_tasks",
    "upsert_task_progress",
    "get_task_progress",
    "upsert_segment",
    "update_segment_progress",
    "get_segment_progress",
    "get_latest_segment_progress",
    "get_unfinished_tasks",
    "count_processing_tasks",
    "append_task_stream_event",
    "list_task_stream_events",
    "request_task_cancel",
    "clear_task_cancel_request",
    "is_task_cancel_requested",
    "upsert_transcription_media_state",
    "get_transcription_media_state",
    "upsert_transcription_translation_segment",
    "get_transcription_translation_segment",
    "list_transcription_translation_segments",
    "clear_transcription_translation_segments",
]
