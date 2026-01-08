<template>
  <div class="app-shell">
    <section class="hero">
      <div class="hero-card">
        <div class="hero-title">MitaHill Better Video</div>
        <p class="hero-subtitle">
          Video and image upscaling powered by Real-ESRGAN. Submit a task, monitor
          progress, and download pristine results once the worker finishes.
        </p>
        <div class="hero-meta">
          <span class="meta-pill">GPU-first pipeline</span>
          <span class="meta-pill">Segmented video flow</span>
          <span class="meta-pill">SQLite + WAL</span>
        </div>
      </div>
      <div class="panel">
        <h2>Quick Stats</h2>
        <p class="notice">Backend: {{ health.status }}</p>
        <p class="notice">Queue DB: {{ health.db }}</p>
        <p class="notice">Worker: {{ health.worker }}</p>
        <button class="secondary" @click="fetchHealth">Refresh</button>
      </div>
    </section>

    <section class="panel-grid">
      <div class="panel">
        <h2>Create Task</h2>

        <div class="field">
          <label>Input Type</label>
          <select v-model="form.inputType">
            <option value="Video">Video</option>
            <option value="Image">Image</option>
          </select>
        </div>

        <div class="field">
          <label>Model</label>
          <select v-model="form.modelName">
            <option value="realesrgan-x4plus">General (High Quality)</option>
            <option value="realesrnet-x4plus">Denoise (Slow)</option>
            <option value="realesrgan-x4plus-anime">Anime</option>
            <option value="realesr-animevideov3">Anime Video</option>
            <option value="realesr-general-x4v3">General (Fast)</option>
          </select>
        </div>

        <div class="field">
          <label>Upscale Factor</label>
          <select v-model.number="form.upscale">
            <option :value="2">2x</option>
            <option :value="3">3x</option>
            <option :value="4">4x</option>
          </select>
        </div>

        <div class="field">
          <label>Tile Size</label>
          <input v-model.number="form.tile" type="number" min="0" max="512" step="64" />
        </div>

        <div class="field" v-if="form.modelName.includes('general')">
          <label>Denoise Strength</label>
          <input v-model.number="form.denoise" type="number" min="0" max="1" step="0.05" />
        </div>

        <div class="field">
          <label>Upload File</label>
          <input type="file" @change="onFileChange" />
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>Keep Original Audio</label>
          <select v-model="form.keepAudio">
            <option :value="true">Yes</option>
            <option :value="false">No</option>
          </select>
        </div>

        <div class="field" v-if="form.inputType === 'Video'">
          <label>CRF (Quality)</label>
          <input v-model.number="form.crf" type="number" min="10" max="30" />
        </div>

        <button @click="submitTask" :disabled="loading.submit">
          {{ loading.submit ? "Submitting..." : "Submit Task" }}
        </button>

        <p v-if="taskId" class="notice" style="margin-top: 12px;">
          Task ID: <strong>{{ taskId }}</strong>
          <button class="secondary" style="margin-left: 8px;" @click="copyTaskId">
            Copy
          </button>
        </p>
        <p v-if="submitError" class="notice" style="color: var(--accent-2);">
          {{ submitError }}
        </p>
      </div>

      <div class="panel">
        <h2>Check Status</h2>

        <div class="field">
          <label>Task ID</label>
          <input v-model="statusQuery" placeholder="Paste Task ID" />
        </div>

        <button class="secondary" @click="fetchStatus">Check</button>

        <div v-if="status" style="margin-top: 16px;">
          <div :class="['status-pill', statusClass]">{{ status.status }}</div>

          <div class="progress" style="margin: 12px 0;">
            <span :style="{ width: status.progress + '%' }"></span>
          </div>
          <p class="notice">{{ status.message }}</p>

          <div class="panel" style="margin-top: 16px; background: rgba(255,255,255,0.05);">
            <p class="notice">File: {{ status.video_info?.filename || 'Unknown' }}</p>
            <p class="notice">Resolution: {{ resolution }}</p>
            <p class="notice">Size: {{ status.video_info?.size_mb || 0 }} MB</p>
          </div>

          <div class="preview-grid" v-if="status.status !== 'PENDING'">
            <div class="preview">
              <p class="notice">Original Preview</p>
              <img
                v-if="preview.original"
                :src="preview.original"
                @load="preview.originalReady = true"
                @error="preview.originalReady = false"
                v-show="preview.originalReady"
              />
              <p v-if="!preview.originalReady" class="notice">Not ready</p>
            </div>
            <div class="preview">
              <p class="notice">Upscaled Preview</p>
              <img
                v-if="preview.upscaled"
                :src="preview.upscaled"
                @load="preview.upscaledReady = true"
                @error="preview.upscaledReady = false"
                v-show="preview.upscaledReady"
              />
              <p v-if="!preview.upscaledReady" class="notice">Not ready</p>
            </div>
          </div>

          <button
            v-if="status.status === 'COMPLETED'"
            style="margin-top: 16px;"
            @click="downloadResult"
          >
            Download Result
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
    submitError.value = "Please select a file before submitting.";
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
      throw new Error(err.error || "Failed to submit task.");
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
    statusError.value = "Please provide a task ID.";
    return;
  }
  try {
    const res = await fetch(`/api/tasks/${statusQuery.value}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || "Task not found.");
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
    submitError.value = "Clipboard not available. Copy manually.";
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
