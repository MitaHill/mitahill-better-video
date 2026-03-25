import { computed, reactive, ref } from "vue";
import { io } from "socket.io-client";
import { buildParamRows, buildProgressDetails, resolveStatusClass } from "./statusViewBuilders";

export const useWorkbenchStatus = ({ parseJsonSafe }) => {
  const taskIds = ref([]);
  const statusQuery = ref("");
  const status = ref(null);
  const statusError = ref("");

  const preview = reactive({
    original: "",
    upscaled: "",
    originalKey: 0,
    upscaledKey: 0,
  });

  const live = reactive({
    gpu: null,
    stage: "",
    itemIndex: 0,
    itemCount: 0,
    itemLabel: "",
    unitDone: 0,
    unitTotal: 0,
    unitLabel: "",
    updatedAtMs: 0,
    segmentIndex: 0,
    segmentCount: 0,
    totalFrame: 0,
    totalFrames: 0,
    segmentFrame: 0,
    segmentTotal: 0,
  });

  const lastPreviewId = ref("");
  const lastPreviewFrame = ref(0);
  const liveNowMs = ref(Date.now());

  let socket = null;
  let pollTimer = null;
  let liveClockTimer = null;

  const toNumber = (value, fallback = 0) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  };

  const toNullableNumber = (value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };

  const normalizeTaskId = (value) => String(value || "").replace(/\D+/g, "").slice(0, 4);

  const normalizeServerTimestamp = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(raw)) return raw;
    if (/^\d{4}-\d{2}-\d{2}T/.test(raw)) return `${raw}Z`;
    if (/^\d{4}-\d{2}-\d{2} /.test(raw)) return `${raw.replace(" ", "T")}Z`;
    return raw;
  };

  const parseUpdatedAtMs = (value) => {
    if (!value) return 0;
    const parsed = Date.parse(normalizeServerTimestamp(value));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const resetLive = () => {
    live.gpu = null;
    live.stage = "";
    live.itemIndex = 0;
    live.itemCount = 0;
    live.itemLabel = "";
    live.unitDone = 0;
    live.unitTotal = 0;
    live.unitLabel = "";
    live.updatedAtMs = 0;
    live.segmentIndex = 0;
    live.segmentCount = 0;
    live.totalFrame = 0;
    live.totalFrames = 0;
    live.segmentFrame = 0;
    live.segmentTotal = 0;
  };

  const inferItemCountFromStatus = (task) => {
    const category = String(task?.task_params?.task_category || "").trim().toLowerCase();
    if (category === "convert") {
      return Array.isArray(task?.task_params?.video_files) ? task.task_params.video_files.length : 0;
    }
    if (category === "transcribe") {
      return Array.isArray(task?.task_params?.media_files) ? task.task_params.media_files.length : 0;
    }
    if (category === "download") {
      return 1;
    }
    return 0;
  };

  const syncLiveFromStatus = (task) => {
    if (!task) return;
    const category = String(task?.task_params?.task_category || "").trim().toLowerCase();
    const taskProgress = task?.task_progress || {};
    const segmentProgress = task?.segment_progress || {};
    const gpuLive = task?.gpu_live || {};

    live.updatedAtMs = parseUpdatedAtMs(task.updated_at) || live.updatedAtMs;
    live.totalFrames = toNumber(taskProgress.total_frames, live.totalFrames);
    const polledGpu = toNullableNumber(gpuLive.utilization_gpu);
    if (polledGpu !== null) {
      // 任务页现在不再完全依赖 socket 事件里的 gpu_util。
      // 轮询接口每次都会带一个当前 GPU 快照，因此就算事件流里没有 GPU 字段，
      // 状态板也能维持一个接近实时的数值。
      live.gpu = polledGpu;
    }

    if (!live.itemCount) {
      live.itemCount = toNumber(taskProgress.total_segments, 0) || inferItemCountFromStatus(task);
    }
    if (!live.itemLabel && live.itemCount) {
      live.itemLabel = category === "enhance" ? "分段" : category === "download" ? "任务" : "文件";
    }

    if (category === "enhance") {
      live.itemIndex = toNumber(segmentProgress.segment_index, live.itemIndex);
      live.unitDone = toNumber(segmentProgress.last_done_frame, live.unitDone);
      live.unitTotal = toNumber(segmentProgress.total_frames, live.unitTotal);
      live.unitLabel = live.unitTotal ? "帧" : live.unitLabel;
      live.segmentIndex = live.itemIndex;
      live.segmentCount = live.itemCount;
      live.segmentFrame = live.unitDone;
      live.segmentTotal = live.unitTotal;
    }
  };

  const isPreviewSupported = computed(() => {
    const category = status.value?.task_params?.task_category || "";
    return category !== "convert" && category !== "transcribe" && category !== "download";
  });

  const resolution = computed(() => {
    if (!status.value?.video_info) return "?";
    const w = status.value.video_info.width || "?";
    const h = status.value.video_info.height || "?";
    if (w === "?" && h === "?") return "-";
    return `${w}x${h}`;
  });

  const paramRows = computed(() => buildParamRows(status.value));
  const statusClass = computed(() => resolveStatusClass(status.value));
  const progressDetails = computed(() => buildProgressDetails(status.value, live, liveNowMs.value));

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
      statusError.value = "请输入 4 位数字任务 ID。";
      return;
    }
    if (statusQuery.value.length !== 4) {
      statusError.value = "任务 ID 必须是 4 位数字。";
      return;
    }

    try {
      const res = await fetch(`/api/tasks/${statusQuery.value}`);
      if (!res.ok) {
        const err = await parseJsonSafe(res);
        if (res.status === 404 || err.error_code === "task_not_found") {
          throw new Error(err.hint || "没有找到这个任务。请确认 4 位任务 ID 是否正确，或该任务已经被系统清理。");
        }
        throw new Error(err.error || "查询任务状态失败，请稍后重试。");
      }

      status.value = await parseJsonSafe(res);
      if (lastPreviewId.value !== statusQuery.value) {
        preview.original = "";
        preview.upscaled = "";
        preview.originalKey = 0;
        preview.upscaledKey = 0;
        lastPreviewId.value = statusQuery.value;
        lastPreviewFrame.value = 0;
        resetLive();
      }
      syncLiveFromStatus(status.value);

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
      stopPolling();
      status.value = null;
      statusError.value = error.message;
    }
  };

  const downloadResult = () => {
    window.location.href = `/api/tasks/${statusQuery.value}/result`;
  };

  const setStatusQuery = (value) => {
    const nextValue = normalizeTaskId(value);
    if (nextValue !== statusQuery.value) {
      resetLive();
      lastPreviewFrame.value = 0;
    }
    statusQuery.value = nextValue;
  };

  const onFrame = (payload) => {
    if (!payload || payload.task_id !== statusQuery.value) return;

    const category = String(payload.task_category || status.value?.task_params?.task_category || "").trim().toLowerCase();
    const nextGpu = toNullableNumber(payload.gpu_util);
    if (nextGpu !== null) {
      // 事件流仍然保留优先级更高的“瞬时值”。
      // 轮询值解决兜底问题，事件值解决刷新更快的问题，两者并存最稳。
      live.gpu = nextGpu;
    }
    live.stage = String(payload.stage || "").trim().toLowerCase() || live.stage;
    live.updatedAtMs = parseUpdatedAtMs(payload.updated_at) || Date.now();
    live.itemIndex = toNumber(payload.item_index ?? payload.segment_index, live.itemIndex);
    live.itemCount = toNumber(payload.item_count ?? payload.segment_count, live.itemCount);
    live.itemLabel =
      String(payload.item_label || "").trim() ||
      live.itemLabel ||
      (live.itemCount ? (category === "enhance" ? "分段" : category === "download" ? "任务" : "文件") : "");
    live.unitDone = toNumber(payload.unit_done ?? payload.segment_frame, live.unitDone);
    live.unitTotal = toNumber(payload.unit_total ?? payload.segment_total, live.unitTotal);
    live.unitLabel = String(payload.unit_label || "").trim() || live.unitLabel || (live.unitTotal ? "帧" : "");
    live.segmentIndex = toNumber(payload.segment_index, live.segmentIndex);
    live.segmentCount = toNumber(payload.segment_count, live.segmentCount);
    live.totalFrame = toNumber(payload.total_frame, live.totalFrame);
    live.totalFrames = toNumber(payload.total_total, live.totalFrames || 0);
    live.segmentFrame = toNumber(payload.segment_frame, live.segmentFrame);
    live.segmentTotal = toNumber(payload.segment_total, live.segmentTotal);

    if (status.value) {
      if (payload.progress !== undefined && payload.progress !== null) {
        status.value.progress = Number(payload.progress) || status.value.progress || 0;
      }
      if (payload.message) {
        status.value.message = payload.message;
      }
      if (payload.updated_at) {
        status.value.updated_at = payload.updated_at;
      }
      if (status.value.task_progress && payload.total_total) {
        status.value.task_progress.total_frames = toNumber(payload.total_total, status.value.task_progress.total_frames || 0);
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
    if (!liveClockTimer) {
      liveClockTimer = setInterval(() => {
        liveNowMs.value = Date.now();
      }, 1000);
    }
  };

  const disposeRealtime = () => {
    stopPolling();
    if (socket) {
      socket.close();
      socket = null;
    }
    if (liveClockTimer) {
      clearInterval(liveClockTimer);
      liveClockTimer = null;
    }
  };

  return {
    taskIds,
    statusQuery,
    status,
    statusError,
    preview,
    live,
    liveNowMs,
    isPreviewSupported,
    resolution,
    paramRows,
    statusClass,
    progressDetails,
    fetchStatus,
    downloadResult,
    joinRoom,
    setStatusQuery,
    initRealtime,
    disposeRealtime,
  };
};
