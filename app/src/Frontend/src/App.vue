<template>
  <div class="app-shell">
    <section class="panel-grid">
      <div class="panel">
        <h2>创建任务</h2>

        <div class="field">
          <label>输入类型</label>
          <select v-model="form.inputType">
            <option value="Video">视频</option>
            <option value="Image">图片</option>
          </select>
        </div>

        <div class="field">
          <label>模型</label>
          <select v-model="form.modelName">
            <option value="realesrgan-x4plus">通用（高清）</option>
            <option value="realesrnet-x4plus">降噪（慢速）</option>
            <option value="realesrgan-x4plus-anime">二次元</option>
            <option value="realesr-animevideov3">二次元视频（快）</option>
            <option value="realesr-general-x4v3">通用（快速）</option>
          </select>
        </div>

        <div class="field">
          <label>放大倍率：{{ form.upscale }}x</label>
          <input
            v-model.number="form.upscale"
            type="range"
            min="2"
            max="4"
            step="1"
          />
        </div>

        <div class="field">
          <label>切片大小：{{ form.tile }}</label>
          <input
            v-model.number="form.tile"
            type="range"
            min="64"
            max="512"
            step="64"
          />
        </div>

        <div class="field" v-if="form.modelName.includes('general')">
          <label>降噪强度：{{ form.denoise.toFixed(2) }}</label>
          <input
            v-model.number="form.denoise"
            type="range"
            min="0"
            max="1"
            step="0.05"
          />
        </div>

        <div class="field">
          <label>上传文件</label>
          <input type="file" @change="onFileChange" />
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>保留原音轨</label>
          <select v-model="form.keepAudio">
            <option :value="true">是</option>
            <option :value="false">否</option>
          </select>
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>音频增强</label>
          <select v-model="form.audioEnhance">
            <option :value="true">启用</option>
            <option :value="false">关闭</option>
          </select>
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>前置降噪</label>
          <select v-model="form.preDenoiseMode">
            <option value="off">关闭</option>
            <option value="speech_enhance">人声增强 (DeepFilterNet2)</option>
            <option value="vhs_hiss">VHS 嘶声降噪</option>
          </select>
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>CRF 质量：{{ form.crf }}</label>
          <input v-model.number="form.crf" type="range" min="10" max="30" />
        </div>

        <button @click="submitTask" :disabled="loading.submit">
          {{ loading.submit ? "提交中..." : "提交任务" }}
        </button>

        <p v-if="taskId" class="notice" style="margin-top: 12px;">
          任务 ID：<strong>{{ taskId }}</strong>
          <button class="secondary" style="margin-left: 8px;" @click="copyTaskId">
            复制
          </button>
        </p>
        <p v-if="submitError" class="notice" style="color: var(--accent-2);">
          {{ submitError }}
        </p>
      </div>

      <div class="panel">
        <h2>查询状态</h2>

        <div class="field">
          <label>任务 ID</label>
          <input v-model="statusQuery" placeholder="粘贴任务 ID" />
        </div>

        <button class="secondary" @click="fetchStatus">查询</button>

        <div v-if="status" style="margin-top: 16px;">
          <div :class="['status-pill', statusClass]">{{ status.status }}</div>

          <div class="progress" style="margin: 12px 0;">
            <span :style="{ width: status.progress + '%' }"></span>
          </div>
          <p class="notice">{{ status.message }}</p>
          <p v-if="progressDetails" class="notice">{{ progressDetails }}</p>

          <div class="panel" style="margin-top: 16px; background: rgba(255,255,255,0.05);">
          <p class="notice">文件：{{ status.video_info?.filename || '未知' }}</p>
          <p class="notice">分辨率：{{ resolution }}</p>
          <p class="notice">大小：{{ status.video_info?.size_mb || 0 }} MB</p>
        </div>

          <div class="preview-grid" v-if="status.status !== 'PENDING'">
            <div class="preview">
              <p class="notice">原始预览</p>
              <img
                v-if="preview.original"
                :key="preview.originalKey"
                :src="preview.original"
                @load="preview.originalReady = true"
                @error="preview.originalReady = false"
                v-show="preview.originalReady"
              />
              <p v-if="!preview.originalReady" class="notice">未生成</p>
            </div>
            <div class="preview">
              <p class="notice">放大预览</p>
              <img
                v-if="preview.upscaled"
                :key="preview.upscaledKey"
                :src="preview.upscaled"
                @load="preview.upscaledReady = true"
                @error="preview.upscaledReady = false"
                v-show="preview.upscaledReady"
              />
              <p v-if="!preview.upscaledReady" class="notice">未生成</p>
            </div>
          </div>

          <button
            v-if="status.status === 'COMPLETED'"
            style="margin-top: 16px;"
            @click="downloadResult"
          >
            下载结果
          </button>
        </div>

        <p v-if="statusError" class="notice" style="color: var(--accent-2); margin-top: 12px;">
          {{ statusError }}
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { io } from "socket.io-client";

const form = reactive({
  inputType: "Video",
  modelName: "realesrgan-x4plus",
  upscale: 3,
  tile: 256,
  denoise: 0.5,
  keepAudio: true,
  audioEnhance: false,
  preDenoiseMode: "off",
  crf: 18,
  file: null
});

const taskId = ref("");
const submitError = ref("");
const statusQuery = ref("");
const status = ref(null);
const statusError = ref("");
const loading = reactive({ submit: false });
const preview = reactive({
  original: "",
  upscaled: "",
  originalKey: 0,
  upscaledKey: 0,
  originalReady: false,
  upscaledReady: false
});
const lastPreviewId = ref("");
const lastPreviewFrame = ref(0);
const live = reactive({
  gpu: null,
  segmentIndex: 0,
  segmentCount: 0,
  totalFrame: 0,
  totalFrames: 0,
  segmentFrame: 0,
  segmentTotal: 0
});
let socket = null;
let pollTimer = null;

const resolution = computed(() => {
  if (!status.value?.video_info) return "?";
  const w = status.value.video_info.width || "?";
  const h = status.value.video_info.height || "?";
  return `${w}x${h}`;
});

const statusClass = computed(() => {
  if (!status.value) return "status-pending";
  const map = {
    PENDING: "status-pending",
    PROCESSING: "status-processing",
    COMPLETED: "status-completed",
    FAILED: "status-failed"
  };
  return map[status.value.status] || "status-pending";
});

const progressDetails = computed(() => {
  if (!status.value) return "";
  const parts = [];
  if (live.gpu !== null) parts.push(`GPU ${live.gpu}%`);
  if (live.totalFrames) parts.push(`总帧 ${live.totalFrame}/${live.totalFrames}`);
  if (live.segmentCount) parts.push(`第${live.segmentIndex}/${live.segmentCount}段`);
  if (live.segmentTotal) parts.push(`分段 ${live.segmentFrame}/${live.segmentTotal}`);
  return parts.join(" | ");
});

const onFileChange = (event) => {
  const file = event.target.files[0];
  if (!file) {
    form.file = null;
    return;
  }
  if (!isFilenameSafe(file.name)) {
    submitError.value = "文件名包含非法字符或过长，请重命名后上传。";
    form.file = null;
    event.target.value = "";
    return;
  }
  form.file = file;
};

const isFilenameSafe = (name) => {
  if (!name || name.length > 180) return false;
  if (name.includes("/") || name.includes("\\")) return false;
  return !/[\u0000-\u001f\u007f]/.test(name);
};

const parseJsonSafe = async (res) => {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  const text = await res.text();
  throw new Error(text || "服务返回非JSON响应。");
};

const submitTask = async () => {
  submitError.value = "";
  if (!form.file) {
    submitError.value = "请先选择要上传的文件。";
    return;
  }
  loading.submit = true;
  try {
    const data = new FormData();
    data.append("file", form.file);
    data.append("input_type", form.inputType);
    data.append("model_name", form.modelName);
    data.append("upscale", String(form.upscale));
    data.append("tile", String(form.tile));
    data.append("denoise_strength", String(form.denoise));
    data.append("keep_audio", String(form.keepAudio));
    data.append("audio_enhance", String(form.audioEnhance));
    data.append("pre_denoise_mode", String(form.preDenoiseMode));
    data.append("crf", String(form.crf));

    const res = await fetch("/api/tasks", { method: "POST", body: data });
    if (!res.ok) {
      const err = await parseJsonSafe(res);
      throw new Error(err.error || "提交失败，请稍后重试。");
    }
    const payload = await parseJsonSafe(res);
    taskId.value = payload.task_id;
    statusQuery.value = payload.task_id;
    joinRoom();
    await fetchStatus();
  } catch (error) {
    submitError.value = error.message;
  } finally {
    loading.submit = false;
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
    const currentId = statusQuery.value;
    if (lastPreviewId.value !== currentId) {
      preview.originalReady = false;
      preview.upscaledReady = false;
      preview.originalKey = 0;
      preview.upscaledKey = 0;
      lastPreviewId.value = currentId;
      lastPreviewFrame.value = 0;
    }
    joinRoom();
    if (status.value.status !== "PROCESSING") {
      const ts = Date.now();
      preview.original = `/api/tasks/${currentId}/preview/original?ts=${ts}`;
      preview.upscaled = `/api/tasks/${currentId}/preview/upscaled?ts=${ts}`;
      preview.originalKey = ts;
      preview.upscaledKey = ts;
      preview.originalReady = false;
      preview.upscaledReady = false;
    }

    if (status.value.status === "PROCESSING" || status.value.status === "PENDING") {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    statusError.value = error.message;
  }
};

const fetchRecommendations = async () => {
  try {
    const res = await fetch("/api/config/recommendations");
    if (!res.ok) return;
    const payload = await res.json();
    if (payload?.tile_size) {
      form.tile = Number(payload.tile_size);
    }
    if (typeof payload?.audio_enhancement_default === "boolean") {
      form.audioEnhance = payload.audio_enhancement_default;
    }
    if (payload?.pre_denoise_default) {
      form.preDenoiseMode = payload.pre_denoise_default;
    }
  } catch (error) {
    // ignore
  }
};

const downloadResult = () => {
  window.location.href = `/api/tasks/${statusQuery.value}/result`;
};

const copyTaskId = async () => {
  if (!taskId.value) return;
  try {
    await navigator.clipboard.writeText(taskId.value);
  } catch (error) {
    submitError.value = "无法访问剪贴板，请手动复制。";
  }
};

const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(fetchStatus, 4000);
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const joinRoom = () => {
  if (socket && statusQuery.value) {
    socket.emit("join", { task_id: statusQuery.value });
  }
};

onMounted(() => {
  fetchRecommendations();
  socket = io();
  socket.on("frame", (payload) => {
    if (!payload || payload.task_id !== statusQuery.value) return;
    live.gpu = payload.gpu_util ?? null;
    live.segmentIndex = payload.segment_index || 0;
    live.segmentCount = payload.segment_count || 0;
    live.totalFrame = payload.total_frame || 0;
    live.totalFrames = payload.total_total || live.totalFrames;
    live.segmentFrame = payload.segment_frame || 0;
    live.segmentTotal = payload.segment_total || 0;
    if (payload.preview_frame) {
      const nextFrame = Number(payload.preview_frame) || 0;
      if (nextFrame >= lastPreviewFrame.value) {
        lastPreviewFrame.value = nextFrame;
        preview.originalReady = false;
        preview.upscaledReady = false;
        preview.originalKey = nextFrame;
        preview.upscaledKey = nextFrame;
        preview.original = `/api/tasks/${payload.task_id}/preview/original?v=${nextFrame}`;
        preview.upscaled = `/api/tasks/${payload.task_id}/preview/upscaled?v=${nextFrame}`;
      }
    }
  });
});
onUnmounted(stopPolling);
</script>
