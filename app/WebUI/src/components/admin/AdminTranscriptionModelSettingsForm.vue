<template>
  <div class="panel admin-card">
    <h2>转录模型设置</h2>
    <p class="notice" style="margin-bottom: 10px;">用于配置默认转录后端、默认模型、运行模式与 aria2 下载行为。</p>

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
        <input
          v-model="local.activeModel"
          list="admin-transcribe-active-model-list"
          :disabled="loading"
          placeholder="例如: medium / large-v3 / distil-large-v3"
        />
        <datalist id="admin-transcribe-active-model-list">
          <option v-for="item in activeModelOptions" :key="item" :value="item" />
        </datalist>
      </div>
    </div>

    <div class="field">
      <label>允许用户可选模型（多选）</label>
      <AdminModernMultiSelect
        :model-value="local.allowedModels"
        :options="activeModelOptions"
        :disabled="loading"
        :allow-custom="true"
        placeholder="搜索模型并回车添加"
        @update:model-value="onAllowedModelsChange"
      />
      <p class="notice" style="margin-top: 6px;">
        候选项会按当前后端过滤并优先展示已安装模型，也可手动输入新模型ID。
      </p>
    </div>

    <div class="param-section" style="margin-top: 10px;">
      <div class="param-title">运行与启动策略</div>
      <div class="inline-grid two">
        <div class="field compact">
          <label>转录运行模式</label>
          <select v-model="local.runtimeMode" :disabled="loading">
            <option value="parallel">并行模式（Whisper常驻，响应更快）</option>
            <option value="memory_saving">节省显存（按阶段卸载/清理）</option>
          </select>
          <p class="notice" style="margin-top: 6px;">
            节省显存模式下会在转录与翻译阶段之间主动释放显存，并在翻译结束后卸载 Ollama 模型（若使用）。
          </p>
        </div>
        <div class="field compact">
          <label class="check-inline" style="margin-top: 24px;">
            <input v-model="local.startupSelfCheckEnabled" :disabled="loading" type="checkbox" />
            启用容器启动自检（增强/转换/转录）
          </label>
          <p class="notice" style="margin-top: 6px;">
            仅支持全局开启/关闭。开启后，任一模块自检失败将中止程序启动并输出详细堆栈日志。
          </p>
        </div>
      </div>
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
import { computed, reactive, watch } from "vue";
import AdminModernMultiSelect from "./AdminModernMultiSelect.vue";

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
  modelOptions: {
    type: Array,
    default: () => [],
  },
});

const local = reactive({
  backend: "whisper",
  activeModel: "medium",
  allowedModels: [],
  aria2: {
    split: 16,
    maxConnectionPerServer: 16,
    maxTries: 10,
    retryWait: 2,
    connectTimeoutSec: 10,
    timeoutSec: 120,
    proxy: "",
  },
  runtimeMode: "parallel",
  startupSelfCheckEnabled: false,
});

const normalizeModelIds = (values) =>
  Array.from(
    new Set(
      (Array.isArray(values) ? values : [])
        .map((item) => String(item || "").trim().toLowerCase())
        .filter((item) => item.length > 0)
    )
  );

const backendOptions = computed(() =>
  normalizeModelIds(
    (Array.isArray(props.modelOptions) ? props.modelOptions : [])
      .filter((item) => String(item?.backend || "").trim().toLowerCase() === String(local.backend || "").trim().toLowerCase())
      .map((item) => item?.model_id)
  )
);

const activeModelOptions = computed(() =>
  normalizeModelIds([
    ...backendOptions.value,
    ...(local.allowedModels || []),
    local.activeModel,
  ])
);

const applyFromProps = () => {
  const cfg = props.configData || {};
  const transcription = cfg.transcription || {};
  const download = cfg.download || {};
  const aria2 = download.aria2 || {};
  local.backend = transcription.backend || "whisper";
  local.activeModel = transcription.active_model || "medium";
  local.allowedModels = normalizeModelIds(transcription.allowed_models || []);
  local.aria2.split = Number(aria2.split ?? 16);
  local.aria2.maxConnectionPerServer = Number(aria2.max_connection_per_server ?? 16);
  local.aria2.maxTries = Number(aria2.max_tries ?? 10);
  local.aria2.retryWait = Number(aria2.retry_wait ?? 2);
  local.aria2.connectTimeoutSec = Number(aria2.connect_timeout_sec ?? 10);
  local.aria2.timeoutSec = Number(aria2.timeout_sec ?? 120);
  local.aria2.proxy = aria2.proxy || "";
  const runtime = cfg.runtime || {};
  local.runtimeMode = runtime.transcribe_runtime_mode || "parallel";
  local.startupSelfCheckEnabled = Boolean(runtime.startup_self_check_enabled);
};

watch(
  () => props.configData,
  () => {
    applyFromProps();
  },
  { immediate: true, deep: true }
);

const onAllowedModelsChange = (nextValues) => {
  local.allowedModels = normalizeModelIds(nextValues);
};

const save = async () => {
  await props.onSave({
    transcription: {
      backend: local.backend,
      active_model: String(local.activeModel || "").trim().toLowerCase(),
      allowed_models: normalizeModelIds(local.allowedModels),
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
    runtime: {
      transcribe_runtime_mode: String(local.runtimeMode || "parallel").trim().toLowerCase(),
      startup_self_check_enabled: Boolean(local.startupSelfCheckEnabled),
    },
  });
};
</script>
