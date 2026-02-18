import { computed, reactive, ref } from "vue";
import { io } from "socket.io-client";
import { buildParamRows, buildProgressDetails, resolveStatusClass } from "./statusViewBuilders";

export const useWorkbenchStatus = ({ parseJsonSafe }) => {
  const taskIds = ref([]);
  const statusQuery = ref("");
  const status = ref(null);
  const statusError = ref("");
  const translationProgressText = ref("");

  const preview = reactive({
    original: "",
    upscaled: "",
    originalKey: 0,
    upscaledKey: 0,
  });

  const live = reactive({
    gpu: null,
    segmentIndex: 0,
    segmentCount: 0,
    totalFrame: 0,
    totalFrames: 0,
    segmentFrame: 0,
    segmentTotal: 0,
  });
  const stream = reactive({
    events: [],
    lines: [],
  });

  const lastPreviewId = ref("");
  const lastPreviewFrame = ref(0);

  let socket = null;
  let pollTimer = null;
  let streamSeenIds = new Set();

  const isPreviewSupported = computed(() => {
    const category = status.value?.task_params?.task_category || "";
    return category !== "convert" && category !== "transcribe" && category !== "download";
  });

  const resolution = computed(() => {
    const info = status.value?.video_info || {};
    const width = Number(info.width || 0);
    const height = Number(info.height || 0);
    if (width > 0 && height > 0) return `${width}x${height}`;
    if (info.has_video === false) return "-";
    return "?x?";
  });

  const paramRows = computed(() => buildParamRows(status.value));
  const statusClass = computed(() => resolveStatusClass(status.value));
  const progressDetails = computed(() => buildProgressDetails(status.value, live));
  const streamLines = computed(() => stream.lines);

  const buildLineKey = (event) =>
    String(
      event.line_key ||
        `${String(event.channel || "general")}::${Number(event.file_index || 0)}::${Number(event.segment_index || 0)}`
    );

  const normalizeStreamEvent = (raw) => {
    if (!raw || typeof raw !== "object") return null;
    const channel = String(raw.channel || raw.stream_channel || "general").trim().toLowerCase();
    const mode = String(raw.mode || raw.stream_mode || "line").trim().toLowerCase();
    if (!["line", "append", "commit"].includes(mode)) return null;
    return {
      id: raw.id ?? raw.stream_event_id ?? null,
      created_at: String(raw.created_at || raw.stream_created_at || ""),
      channel,
      mode,
      line_key: String(raw.line_key || raw.stream_line_key || "").trim(),
      text: String(raw.text || raw.stream_text || ""),
      file_index: Number(raw.file_index || 0),
      file_count: Number(raw.file_count || 0),
      segment_index: Number(raw.segment_index || 0),
    };
  };

  const rebuildStreamLines = () => {
    const activeLineIndex = new Map();
    const out = [];
    for (const event of stream.events) {
      if (String(event.channel || "").trim().toLowerCase() === "translation_progress") {
        continue;
      }
      const mode = String(event.mode || "").trim().toLowerCase();
      const key = buildLineKey(event);
      if (mode === "commit") {
        activeLineIndex.delete(key);
        continue;
      }
      if (mode === "append") {
        const existingIdx = activeLineIndex.get(key);
        if (existingIdx === undefined) {
          out.push({
            id: event.id || null,
            channel: event.channel,
            text: String(event.text || ""),
            file_index: event.file_index,
            file_count: event.file_count,
            segment_index: event.segment_index,
            created_at: event.created_at,
            line_key: key,
          });
          activeLineIndex.set(key, out.length - 1);
        } else {
          out[existingIdx].text = `${String(out[existingIdx].text || "")}${String(event.text || "")}`;
          out[existingIdx].id = event.id || out[existingIdx].id;
        }
        continue;
      }
      out.push({
        id: event.id || null,
        channel: event.channel,
        text: String(event.text || ""),
        file_index: event.file_index,
        file_count: event.file_count,
        segment_index: event.segment_index,
        created_at: event.created_at,
        line_key: key,
      });
    }
    const maxLines = 600;
    stream.lines = out.length > maxLines ? out.slice(out.length - maxLines) : out;
  };

  const refreshTranslationProgressText = () => {
    translationProgressText.value = "";
    for (let i = stream.events.length - 1; i >= 0; i -= 1) {
      const event = stream.events[i];
      if (String(event?.channel || "").trim().toLowerCase() !== "translation_progress") continue;
      const text = String(event?.text || "").trim();
      if (!text) continue;
      translationProgressText.value = text;
      return;
    }
  };

  const replaceStreamEvents = (events) => {
    const normalized = [];
    streamSeenIds = new Set();
    for (const item of Array.isArray(events) ? events : []) {
      const safe = normalizeStreamEvent(item);
      if (!safe) continue;
      const eventId = safe.id == null ? "" : String(safe.id);
      if (eventId && streamSeenIds.has(eventId)) continue;
      if (eventId) streamSeenIds.add(eventId);
      normalized.push(safe);
    }
    stream.events = normalized;
    rebuildStreamLines();
    refreshTranslationProgressText();
  };

  const appendStreamEvent = (event) => {
    const safe = normalizeStreamEvent(event);
    if (!safe) return;
    const eventId = safe.id == null ? "" : String(safe.id);
    if (eventId && streamSeenIds.has(eventId)) return;
    if (eventId) streamSeenIds.add(eventId);
    stream.events.push(safe);
    if (stream.events.length > 3000) {
      stream.events = stream.events.slice(stream.events.length - 3000);
      streamSeenIds = new Set(
        stream.events.map((item) => (item.id == null ? "" : String(item.id))).filter((item) => item.length > 0)
      );
    }
    rebuildStreamLines();
    refreshTranslationProgressText();
  };

  const swapPreview = (kind, url) => {
    const img = new Image();
    img.onload = () => {
      if (kind === "original") {
        preview.original = url;
        preview.originalKey += 1;
      } else {
        preview.upscaled = url;
        preview.upscaledKey += 1;
      }
    };
    img.src = url;
  };

  const startPolling = (fetchStatus) => {
    if (pollTimer) return;
    pollTimer = setInterval(fetchStatus, 4000);
  };

  const stopPolling = () => {
    if (!pollTimer) return;
    clearInterval(pollTimer);
    pollTimer = null;
  };

  const joinRoom = () => {
    if (socket && statusQuery.value) {
      socket.emit("join", { task_id: statusQuery.value });
    }
  };

  const fetchStatus = async () => {
    statusError.value = "";
    if (!statusQuery.value) {
      statusError.value = "请先填写任务 ID。";
      return;
    }

    try {
      const res = await fetch(`/api/tasks/${statusQuery.value}?stream_limit=800`);
      if (!res.ok) {
        const err = await parseJsonSafe(res);
        throw new Error(err.error || "未找到任务，请确认 ID 是否正确。");
      }

      status.value = await parseJsonSafe(res);
      replaceStreamEvents(status.value.stream_events || []);
      if (!translationProgressText.value) {
        const fallbackMessage = String(status.value?.message || "").trim();
        if (fallbackMessage.includes("翻译")) {
          translationProgressText.value = fallbackMessage;
        }
      }
      if (lastPreviewId.value !== statusQuery.value) {
        preview.original = "";
        preview.upscaled = "";
        preview.originalKey = 0;
        preview.upscaledKey = 0;
        lastPreviewId.value = statusQuery.value;
        lastPreviewFrame.value = 0;
        replaceStreamEvents(status.value.stream_events || []);
      }

      joinRoom();

      if (isPreviewSupported.value) {
        const ts = Date.now();
        swapPreview("original", `/api/tasks/${statusQuery.value}/preview/original?ts=${ts}`);
        swapPreview("upscaled", `/api/tasks/${statusQuery.value}/preview/upscaled?ts=${ts}`);
      }

      if (status.value.status === "PROCESSING" || status.value.status === "PENDING") {
        startPolling(fetchStatus);
      } else {
        stopPolling();
      }
    } catch (error) {
      statusError.value = error.message;
    }
  };

  const downloadResult = () => {
    window.location.href = `/api/tasks/${statusQuery.value}/result`;
  };

  const setStatusQuery = (value) => {
    statusQuery.value = String(value || "");
    translationProgressText.value = "";
  };

  const onFrame = (payload) => {
    if (!payload || payload.task_id !== statusQuery.value) return;

    if (String(payload.event_type || "").trim().toLowerCase() === "task_stream") {
      appendStreamEvent(payload);
      return;
    }

    live.gpu = payload.gpu_util ?? null;
    live.segmentIndex = payload.segment_index || 0;
    live.segmentCount = payload.segment_count || 0;
    live.totalFrame = payload.total_frame || 0;
    live.totalFrames = payload.total_total || live.totalFrames;
    live.segmentFrame = payload.segment_frame || 0;
    live.segmentTotal = payload.segment_total || 0;

    if (status.value) {
      if (payload.progress !== undefined && payload.progress !== null) {
        status.value.progress = Number(payload.progress) || status.value.progress || 0;
      }
      if (payload.message) {
        status.value.message = payload.message;
      }
    }

    if (payload.preview_frame && isPreviewSupported.value) {
      const nextFrame = Number(payload.preview_frame) || 0;
      const shouldReset = payload.preview_reset === true;
      if (shouldReset || nextFrame >= lastPreviewFrame.value) {
        lastPreviewFrame.value = nextFrame;
        swapPreview("original", `/api/tasks/${payload.task_id}/preview/original?v=${nextFrame}`);
        swapPreview("upscaled", `/api/tasks/${payload.task_id}/preview/upscaled?v=${nextFrame}`);
      }
    }
  };

  const initRealtime = () => {
    socket = io();
    socket.on("frame", onFrame);
  };

  const disposeRealtime = () => {
    stopPolling();
    if (socket) {
      socket.close();
      socket = null;
    }
  };

  return {
    taskIds,
    statusQuery,
    status,
    statusError,
    translationProgressText,
    preview,
    isPreviewSupported,
    resolution,
    paramRows,
    statusClass,
    progressDetails,
    streamLines,
    fetchStatus,
    downloadResult,
    joinRoom,
    setStatusQuery,
    initRealtime,
    disposeRealtime,
  };
};
