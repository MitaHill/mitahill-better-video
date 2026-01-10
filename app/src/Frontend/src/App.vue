<template>
  <div class="app-shell">
    <div class="app-header">
      <h1 class="app-title">更好的视频</h1>
    </div>
    <section class="panel-grid">
      <div class="panel">
        <h2>创建任务</h2>

        <div class="param-group">
          <div class="param-section">
            <div class="param-title">任务基础</div>
            <div class="field">
              <label>输入类型</label>
              <select v-model="form.inputType">
                <option value="Video">视频</option>
                <option value="Image">图片</option>
              </select>
            </div>
            <div class="field">
              <label>上传文件</label>
              <input type="file" multiple @change="onFileChange" />
            </div>
            <p v-if="form.inputType === 'Video'" class="notice">
              仅支持 H.264/H.265 视频 + AAC 音频（拒绝 AV1/VP9/非 AAC）。
            </p>
          </div>

          <div class="param-section">
            <div class="param-title">画面参数</div>
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
          </div>

          <div class="param-section" v-if="form.inputType === 'Video'">
            <div class="param-title">音频参数</div>
            <div class="field">
              <label>保留原音轨</label>
              <select v-model="form.keepAudio">
                <option :value="true">是</option>
                <option :value="false">否</option>
              </select>
            </div>
            <div class="field">
              <label>音频增强</label>
              <select v-model="form.audioEnhance">
                <option :value="true">启用</option>
                <option :value="false">关闭</option>
              </select>
            </div>
            <div class="field">
              <label>前置降噪</label>
              <select v-model="form.preDenoiseMode">
                <option value="off">关闭</option>
                <option value="speech_enhance">人声增强 (DeepFilterNet2)</option>
                <option value="vhs_hiss">VHS 嘶声降噪</option>
              </select>
            </div>
            <div class="field">
              <label>哈斯效应</label>
              <div class="haas-row">
                <label class="haas-toggle">
                  <input type="checkbox" v-model="form.haasEnabled" />
                  启用
                </label>
                <select v-model="form.haasLead" :disabled="!form.haasEnabled">
                  <option value="left">左声道先出声</option>
                  <option value="right">右声道先出声</option>
                </select>
              </div>
              <div class="haas-controls">
                <input
                  v-model.number="form.haasDelayMs"
                  type="range"
                  min="0"
                  max="3000"
                  step="1"
                  :disabled="!form.haasEnabled"
                />
                <div class="haas-input">
                  <input
                    v-model.number="form.haasDelayMs"
                    type="number"
                    min="0"
                    max="3000"
                    step="1"
                    :disabled="!form.haasEnabled"
                  />
                  <span>ms</span>
                </div>
              </div>
              <p class="notice">0 ms 仅转换单声道为双声道；>0 ms 应用哈斯延迟。</p>
            </div>
          </div>

          <div class="param-section" v-if="form.inputType === 'Video'">
            <div class="param-title">编码参数</div>
            <div class="field">
              <label>CRF 质量：{{ form.crf }}</label>
              <input v-model.number="form.crf" type="range" min="10" max="30" />
            </div>
          </div>
        </div>

        <button @click="submitTask" :disabled="loading.submit">
          {{ loading.submit ? "提交中..." : "提交任务" }}
        </button>

        <div v-if="taskIds.length" class="notice task-id-panel" style="margin-top: 12px;">
          <div class="task-id-header">
            <span>任务 ID：</span>
          </div>
          <div class="task-id-list">
            <span v-for="id in taskIds" :key="id" class="task-id-chip">
              {{ id }}
            </span>
          </div>
        </div>
        <p v-if="submitError" class="notice" style="color: var(--accent-2);">
          {{ submitError }}
        </p>
        <p v-if="submitWarnings" class="notice" style="color: var(--text-muted);">
          {{ submitWarnings }}
        </p>
      </div>

      <div class="panel">
        <h2>查询状态</h2>

        <div class="field">
          <label>任务 ID</label>
          <input v-model="statusQuery" placeholder="粘贴任务 ID" />
        </div>

        <div class="status-row">
          <button class="secondary" @click="fetchStatus">查询</button>
          <div v-if="status" :class="['status-pill', statusClass]">
            {{ status.status }}
          </div>
        </div>

        <div v-if="status" style="margin-top: 16px;">
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
              />
              <p v-if="!preview.original" class="notice">未生成</p>
            </div>
            <div class="preview">
              <p class="notice">放大预览</p>
              <img
                v-if="preview.upscaled"
                :key="preview.upscaledKey"
                :src="preview.upscaled"
              />
              <p v-if="!preview.upscaled" class="notice">未生成</p>
            </div>
          </div>

          <div class="param-table" v-if="status.task_params" style="margin-top: 16px;">
            <div class="param-table-title">任务参数</div>
            <table>
              <tbody>
                <tr v-for="row in paramRows" :key="row.label">
                  <th>{{ row.label }}</th>
                  <td>{{ row.value }}</td>
                </tr>
              </tbody>
            </table>
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
    <div class="app-signature">由CodeX和米塔山开发</div>
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
  haasEnabled: false,
  haasDelayMs: 0,
  haasLead: "left",
  crf: 18,
  file: null,
  files: []
});

const taskIds = ref([]);
const submitError = ref("");
const submitWarnings = ref("");
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

const formatBool = (val) => (val ? "是" : "否");
const formatHaas = (params) => {
  if (!params?.haas_enabled) return "关闭";
  const delay = Number(params?.haas_delay_ms || 0);
  const lead = params?.haas_lead === "right" ? "右声道先出声" : "左声道先出声";
  return `${delay} ms (${lead})`;
};

const paramRows = computed(() => {
  const params = status.value?.task_params || {};
  return [
    { label: "输入类型", value: params.input_type || "-" },
    { label: "模型", value: params.model_name || "-" },
    { label: "放大倍率", value: params.upscale ? `${params.upscale}x` : "-" },
    { label: "切片大小", value: params.tile ?? "-" },
    { label: "降噪强度", value: params.denoise_strength ?? "-" },
    { label: "保留原音轨", value: params.keep_audio !== undefined ? formatBool(params.keep_audio) : "-" },
    { label: "音频增强", value: params.audio_enhance !== undefined ? formatBool(params.audio_enhance) : "-" },
    { label: "前置降噪", value: params.pre_denoise_mode || "-" },
    { label: "哈斯效应", value: formatHaas(params) },
    { label: "CRF 质量", value: params.crf ?? "-" },
    { label: "Tile Pad", value: params.tile_pad ?? "-" },
    { label: "FP16", value: params.fp16 !== undefined ? formatBool(params.fp16) : "-" },
  ];
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
  const fallbackProgress = status.value.task_progress || {};
  const fallbackSegment = status.value.segment_progress || {};
  const totalFrames = live.totalFrames || fallbackProgress.total_frames || 0;
  const segmentCount = live.segmentCount || fallbackProgress.total_segments || 0;
  const segmentIndex = live.segmentIndex || fallbackSegment.segment_index || 0;
  const segmentTotal = live.segmentTotal || fallbackSegment.total_frames || 0;
  const segmentFrame = live.segmentFrame || fallbackSegment.last_done_frame || 0;
  const totalFrame =
    live.totalFrame ||
    (fallbackSegment.start_frame
      ? Math.max(0, Number(fallbackSegment.start_frame) + Number(segmentFrame) - 1)
      : 0);
  const parts = [];
  if (live.gpu !== null) parts.push(`GPU ${live.gpu}%`);
  if (totalFrames) parts.push(`总帧 ${totalFrame}/${totalFrames}`);
  if (segmentCount) parts.push(`第${segmentIndex}/${segmentCount}段`);
  if (segmentTotal) parts.push(`分段 ${segmentFrame}/${segmentTotal}`);
  return parts.join(" | ");
});

const onFileChange = (event) => {
  const files = Array.from(event.target.files || []);
  if (!files.length) {
    form.file = null;
    form.files = [];
    return;
  }
  if (files.some((f) => !isFilenameSafe(f.name))) {
    submitError.value = "文件名包含非法字符或过长，请重命名后上传。";
    form.file = null;
    form.files = [];
    event.target.value = "";
    return;
  }
  form.files = files;
  form.file = files[0] || null;
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
  submitWarnings.value = "";
  if (!form.files || form.files.length === 0) {
    submitError.value = "请先选择要上传的文件。";
    return;
  }
  if (form.haasDelayMs < 0) form.haasDelayMs = 0;
  if (form.haasDelayMs > 3000) form.haasDelayMs = 3000;
  loading.submit = true;
  try {
    const data = new FormData();
    if (form.files.length > 1) {
      form.files.forEach((file) => data.append("files", file));
    } else {
      data.append("file", form.files[0]);
    }
    data.append("input_type", form.inputType);
    data.append("model_name", form.modelName);
    data.append("upscale", String(form.upscale));
    data.append("tile", String(form.tile));
    data.append("denoise_strength", String(form.denoise));
    data.append("keep_audio", String(form.keepAudio));
    data.append("audio_enhance", String(form.audioEnhance));
    data.append("pre_denoise_mode", String(form.preDenoiseMode));
    data.append("haas_enabled", String(form.haasEnabled));
    data.append("haas_delay_ms", String(form.haasDelayMs));
    data.append("haas_lead", String(form.haasLead));
    data.append("crf", String(form.crf));

    const endpoint = form.files.length > 1 ? "/api/tasks/batch" : "/api/tasks";
    const res = await fetch(endpoint, { method: "POST", body: data });
    if (!res.ok) {
      const err = await parseJsonSafe(res);
      if (err.task_id) {
        taskIds.value = [err.task_id];
        statusQuery.value = err.task_id;
      }
      throw new Error(err.error || "提交失败，请稍后重试。");
    }
    const payload = await parseJsonSafe(res);
    if (endpoint.endsWith("/batch")) {
      taskIds.value = payload.task_ids || [];
      if (payload.errors && payload.errors.length) {
        submitWarnings.value = payload.errors.map(e => `${e.filename}: ${e.error}`).join("；");
      }
      if (taskIds.value.length) {
        statusQuery.value = taskIds.value[0];
        joinRoom();
        await fetchStatus();
      }
    } else {
      taskIds.value = [payload.task_id];
      statusQuery.value = payload.task_id;
      joinRoom();
      await fetchStatus();
    }
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
      preview.originalKey = 0;
      preview.upscaledKey = 0;
      preview.original = "";
      preview.upscaled = "";
      preview.originalReady = false;
      preview.upscaledReady = false;
      lastPreviewId.value = currentId;
      lastPreviewFrame.value = 0;
    }
    joinRoom();
    if (status.value.status !== "PROCESSING") {
      const ts = Date.now();
      swapPreview("original", `/api/tasks/${currentId}/preview/original?ts=${ts}`);
      swapPreview("upscaled", `/api/tasks/${currentId}/preview/upscaled?ts=${ts}`);
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

const swapPreview = (kind, url) => {
  const img = new Image();
  img.onload = () => {
    if (kind === "original") {
      preview.original = url;
      preview.originalKey += 1;
      preview.originalReady = true;
    } else {
      preview.upscaled = url;
      preview.upscaledKey += 1;
      preview.upscaledReady = true;
    }
  };
  img.onerror = () => {
    if (kind === "original" && !preview.original) preview.originalReady = false;
    if (kind === "upscaled" && !preview.upscaled) preview.upscaledReady = false;
  };
  img.src = url;
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
        swapPreview("original", `/api/tasks/${payload.task_id}/preview/original?v=${nextFrame}`);
        swapPreview("upscaled", `/api/tasks/${payload.task_id}/preview/upscaled?v=${nextFrame}`);
      }
    }
  });
});
onUnmounted(stopPolling);
</script>
