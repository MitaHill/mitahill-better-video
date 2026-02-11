<template>
  <div class="panel admin-card">
    <h2>转录模型设置</h2>
    <p class="notice" style="margin-bottom: 10px;">用于配置默认转录后端、默认模型和 aria2 下载行为。</p>

    <div class="inline-grid two">
      <div class="field compact">
        <label>默认后端</label>
        <select v-model="local.backend" :disabled="loading">
          <option value="whisper">openai-whisper</option>
          <option value="faster_whisper">faster-whisper</option>
        </select>
      </div>
      <div class="field compact">
        <label>默认模型</label>
        <input v-model="local.activeModel" :disabled="loading" placeholder="例如: medium / large-v3 / distil-large-v3" />
      </div>
    </div>

    <div class="field">
      <label>允许用户可选模型（逗号分隔）</label>
      <textarea v-model="local.allowedModelsRaw" :disabled="loading" rows="3" placeholder="tiny,base,small,medium,large-v3,turbo"></textarea>
    </div>

    <div class="param-section" style="margin-top: 10px;">
      <div class="param-title">aria2 下载参数</div>
      <div class="inline-grid four">
        <div class="field compact">
          <label>split</label>
          <input v-model.number="local.aria2.split" :disabled="loading" type="number" min="1" max="64" />
        </div>
        <div class="field compact">
          <label>最大连接</label>
          <input v-model.number="local.aria2.maxConnectionPerServer" :disabled="loading" type="number" min="1" max="64" />
        </div>
        <div class="field compact">
          <label>重试次数</label>
          <input v-model.number="local.aria2.maxTries" :disabled="loading" type="number" min="1" max="100" />
        </div>
        <div class="field compact">
          <label>重试间隔(s)</label>
          <input v-model.number="local.aria2.retryWait" :disabled="loading" type="number" min="1" max="30" />
        </div>
      </div>

      <div class="inline-grid two">
        <div class="field compact">
          <label>连接超时(s)</label>
          <input v-model.number="local.aria2.connectTimeoutSec" :disabled="loading" type="number" min="3" max="120" />
        </div>
        <div class="field compact">
          <label>下载超时(s)</label>
          <input v-model.number="local.aria2.timeoutSec" :disabled="loading" type="number" min="10" max="600" />
        </div>
      </div>

      <div class="field compact" style="margin-top: 8px;">
        <label>下载代理（支持 socks5/http）</label>
        <input v-model="local.aria2.proxy" :disabled="loading" placeholder="例如: socks5://127.0.0.1:1080" />
      </div>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button :disabled="loading" type="button" @click="save">{{ loading ? "保存中..." : "保存模型设置" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
  configData: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  error: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  onSave: {
    type: Function,
    required: true,
  },
});

const local = reactive({
  backend: "whisper",
  activeModel: "medium",
  allowedModelsRaw: "",
  aria2: {
    split: 16,
    maxConnectionPerServer: 16,
    maxTries: 10,
    retryWait: 2,
    connectTimeoutSec: 10,
    timeoutSec: 120,
    proxy: "",
  },
});

const applyFromProps = () => {
  const cfg = props.configData || {};
  const transcription = cfg.transcription || {};
  const download = cfg.download || {};
  const aria2 = download.aria2 || {};
  local.backend = transcription.backend || "whisper";
  local.activeModel = transcription.active_model || "medium";
  local.allowedModelsRaw = Array.isArray(transcription.allowed_models)
    ? transcription.allowed_models.join(",")
    : "";
  local.aria2.split = Number(aria2.split ?? 16);
  local.aria2.maxConnectionPerServer = Number(aria2.max_connection_per_server ?? 16);
  local.aria2.maxTries = Number(aria2.max_tries ?? 10);
  local.aria2.retryWait = Number(aria2.retry_wait ?? 2);
  local.aria2.connectTimeoutSec = Number(aria2.connect_timeout_sec ?? 10);
  local.aria2.timeoutSec = Number(aria2.timeout_sec ?? 120);
  local.aria2.proxy = aria2.proxy || "";
};

watch(
  () => props.configData,
  () => {
    applyFromProps();
  },
  { immediate: true, deep: true }
);

const save = async () => {
  const allowedModels = String(local.allowedModelsRaw || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter((item) => item.length > 0);

  await props.onSave({
    transcription: {
      backend: local.backend,
      active_model: String(local.activeModel || "").trim().toLowerCase(),
      allowed_models: allowedModels,
    },
    download: {
      aria2: {
        split: Number(local.aria2.split || 16),
        max_connection_per_server: Number(local.aria2.maxConnectionPerServer || 16),
        max_tries: Number(local.aria2.maxTries || 10),
        retry_wait: Number(local.aria2.retryWait || 2),
        connect_timeout_sec: Number(local.aria2.connectTimeoutSec || 10),
        timeout_sec: Number(local.aria2.timeoutSec || 120),
        proxy: String(local.aria2.proxy || "").trim(),
      },
    },
  });
};
</script>
