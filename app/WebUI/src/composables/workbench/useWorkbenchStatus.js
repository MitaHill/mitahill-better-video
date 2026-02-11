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
    segmentIndex: 0,
    segmentCount: 0,
    totalFrame: 0,
    totalFrames: 0,
    segmentFrame: 0,
    segmentTotal: 0,
  });

  const lastPreviewId = ref("");
  const lastPreviewFrame = ref(0);

  let socket = null;
  let pollTimer = null;

  const isPreviewSupported = computed(() => {
    const category = status.value?.task_params?.task_category || "";
    return category !== "convert" && category !== "transcribe" && category !== "download";
  });

  const resolution = computed(() => {
    if (!status.value?.video_info) return "?";
    const w = status.value.video_info.width || "?";
    const h = status.value.video_info.height || "?";
    return `${w}x${h}`;
  });

  const paramRows = computed(() => buildParamRows(status.value));
  const statusClass = computed(() => resolveStatusClass(status.value));
  const progressDetails = computed(() => buildProgressDetails(status.value, live));

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
      const res = await fetch(`/api/tasks/${statusQuery.value}`);
      if (!res.ok) {
        const err = await parseJsonSafe(res);
        throw new Error(err.error || "未找到任务，请确认 ID 是否正确。");
      }

      status.value = await parseJsonSafe(res);
      if (lastPreviewId.value !== statusQuery.value) {
        preview.original = "";
        preview.upscaled = "";
        preview.originalKey = 0;
        preview.upscaledKey = 0;
        lastPreviewId.value = statusQuery.value;
        lastPreviewFrame.value = 0;
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
  };

  const onFrame = (payload) => {
    if (!payload || payload.task_id !== statusQuery.value) return;

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
    preview,
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
