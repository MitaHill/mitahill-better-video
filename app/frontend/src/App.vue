<template>
  <div class="app-shell">
    <section class="hero">
      <div class="hero-card">
        <div class="hero-title">米塔影像增强平台</div>
        <p class="hero-subtitle">
          提交任务、查看进度、下载结果，一站式完成视频与图片增强。
        </p>
      </div>
      <div class="panel">
        <h2>服务状态</h2>
        <p class="notice">后端：{{ health.status }}</p>
        <p class="notice">数据库：{{ health.db }}</p>
        <p class="notice">Worker：{{ health.worker }}</p>
        <button class="secondary" @click="fetchHealth">刷新</button>
      </div>
    </section>

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
            min="0"
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

const form = reactive({
  inputType: "Video",
  modelName: "realesrgan-x4plus",
  upscale: 3,
  tile: 256,
  denoise: 0.5,
  keepAudio: true,
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
  originalReady: false,
  upscaledReady: false
});
const health = reactive({ status: "unknown", db: "unknown", worker: "unknown" });
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

const onFileChange = (event) => {
  const file = event.target.files[0];
  form.file = file || null;
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
    data.append("crf", String(form.crf));

    const res = await fetch("/api/tasks", { method: "POST", body: data });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "提交失败，请稍后重试。");
    }
    const payload = await res.json();
    taskId.value = payload.task_id;
    statusQuery.value = payload.task_id;
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
      const err = await res.json();
      throw new Error(err.error || "未找到任务，请确认 ID 是否正确。");
    }
    status.value = await res.json();
    preview.original = `/api/tasks/${statusQuery.value}/preview/original`;
    preview.upscaled = `/api/tasks/${statusQuery.value}/preview/upscaled`;
    preview.originalReady = false;
    preview.upscaledReady = false;

    if (status.value.status === "PROCESSING" || status.value.status === "PENDING") {
      startPolling();
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

const copyTaskId = async () => {
  if (!taskId.value) return;
  try {
    await navigator.clipboard.writeText(taskId.value);
  } catch (error) {
    submitError.value = "无法访问剪贴板，请手动复制。";
  }
};

const fetchHealth = async () => {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("Health check failed");
    const payload = await res.json();
    health.status = payload.status || "ok";
    health.db = payload.db || "unknown";
    health.worker = payload.worker || "unknown";
  } catch (error) {
    health.status = "offline";
    health.db = "unknown";
    health.worker = "unknown";
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

onMounted(fetchHealth);
onUnmounted(stopPolling);
</script>
