<template>
  <div class="panel admin-card">
    <h2>调试工具</h2>

    <div class="inline-grid two" style="margin-top: 10px;">
      <div class="param-section">
        <div class="param-title">测试转录模型</div>
        <p class="notice" style="margin-bottom: 10px;">步骤：目标解析 -> HASH 校验 -> GPU 热身识别 5 秒静音音频</p>
        <div class="field compact" style="margin-bottom: 10px;">
          <label>测试目标（已安装模型）</label>
          <select v-model="selectedTarget" :disabled="loadingModel || !modelTargetOptions.length">
            <option v-for="item in modelTargetOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </div>
        <p v-if="!modelTargetOptions.length" class="notice" style="color: var(--accent-2); margin-bottom: 10px;">
          暂无已安装模型，请先在“模型目录与下载”中下载模型。
        </p>
        <button type="button" :disabled="loadingModel || !selectedTarget" @click="triggerModelTest">
          {{ loadingModel ? "测试中..." : "测试转录模型" }}
        </button>
        <div v-if="modelSteps.length" class="debug-step-list">
          <div
            v-for="step in modelSteps"
            :key="step.key"
            class="debug-step-item"
            :class="`is-${step.status}`"
          >
            <div class="debug-step-head">
              <span>{{ step.label }}</span>
              <strong>{{ toStatusLabel(step.status) }}</strong>
            </div>
            <p class="notice" style="margin: 6px 0 0;">{{ step.message || "-" }}</p>
          </div>
        </div>
        <p v-if="modelError" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ modelError }}</p>
        <pre v-if="modelResult" class="mono" style="margin-top: 8px; white-space: pre-wrap;">{{ stringify(modelResult) }}</pre>
      </div>

      <div class="param-section">
        <div class="param-title">测试翻译源</div>
        <p class="notice" style="margin-bottom: 10px;">支持 Ollama TCP-PING、模型列表检查、对话耗时评估，以及 OpenAI 兼容错误诊断。</p>
        <button type="button" :disabled="loadingTranslation" @click="onTestTranslation">
          {{ loadingTranslation ? "测试中..." : "测试翻译源" }}
        </button>
        <p v-if="translationError" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ translationError }}</p>
        <pre v-if="translationResult" class="mono" style="margin-top: 8px; white-space: pre-wrap;">{{ stringify(translationResult) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  loadingModel: {
    type: Boolean,
    required: true,
  },
  transcriptionModels: {
    type: Array,
    default: () => [],
  },
  transcriptionConfig: {
    type: Object,
    default: () => ({}),
  },
  modelError: {
    type: String,
    required: true,
  },
  modelResult: {
    type: [Object, Array, String, Number, Boolean],
    default: null,
  },
  modelSteps: {
    type: Array,
    default: () => [],
  },
  loadingTranslation: {
    type: Boolean,
    required: true,
  },
  translationError: {
    type: String,
    required: true,
  },
  translationResult: {
    type: [Object, Array, String, Number, Boolean],
    default: null,
  },
  onTestModel: {
    type: Function,
    required: true,
  },
  onTestTranslation: {
    type: Function,
    required: true,
  },
});

const selectedTarget = ref("");

const modelTargetOptions = computed(() => {
  const rows = Array.isArray(props.transcriptionModels) ? props.transcriptionModels : [];
  const out = [];
  const seen = new Set();
  for (const row of rows) {
    if (!row || !row.installed) continue;
    const backend = String(row.backend || "").trim().toLowerCase();
    const modelId = String(row.model_id || "").trim().toLowerCase();
    if (!backend || !modelId) continue;
    const key = `${backend}::${modelId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      value: key,
      backend,
      modelId,
      label: `${backend === "faster_whisper" ? "fast-whisper" : backend} / ${modelId}`,
    });
  }
  out.sort((a, b) => a.label.localeCompare(b.label));
  return out;
});

const _ensureSelection = () => {
  const options = modelTargetOptions.value;
  if (!options.length) {
    selectedTarget.value = "";
    return;
  }

  const hasCurrent = options.some((item) => item.value === selectedTarget.value);
  if (hasCurrent) return;

  const cfg = props.transcriptionConfig || {};
  const transcription = cfg.transcription || {};
  const backend = String(transcription.backend || "").trim().toLowerCase();
  const modelId = String(transcription.active_model || "").trim().toLowerCase();
  const preferredKey = `${backend}::${modelId}`;
  const preferred = options.find((item) => item.value === preferredKey);
  selectedTarget.value = preferred ? preferred.value : options[0].value;
};

watch(
  () => modelTargetOptions.value.map((item) => item.value).join("|"),
  () => _ensureSelection(),
  { immediate: true }
);

watch(
  () => JSON.stringify((props.transcriptionConfig || {}).transcription || {}),
  () => _ensureSelection()
);

const triggerModelTest = () => {
  if (!selectedTarget.value) return;
  const [backend, modelId] = String(selectedTarget.value).split("::");
  props.onTestModel({
    backend: String(backend || "").trim().toLowerCase(),
    modelId: String(modelId || "").trim().toLowerCase(),
  });
};

const toStatusLabel = (status) => {
  const key = String(status || "").trim().toLowerCase();
  if (key === "running") return "进行中";
  if (key === "passed") return "通过";
  if (key === "failed") return "失败";
  return "等待";
};

const stringify = (value) => JSON.stringify(value || {}, null, 2);
</script>

<style scoped>
.debug-step-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-top: 10px;
}

.debug-step-item {
  border: 1px solid var(--panel-border);
  border-left-width: 3px;
  border-radius: 6px;
  padding: 8px 10px;
  background: color-mix(in srgb, var(--panel-bg) 84%, transparent);
}

.debug-step-item.is-running {
  border-left-color: var(--accent);
}

.debug-step-item.is-passed {
  border-left-color: #39b86f;
}

.debug-step-item.is-failed {
  border-left-color: var(--accent-2);
}

.debug-step-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
</style>
