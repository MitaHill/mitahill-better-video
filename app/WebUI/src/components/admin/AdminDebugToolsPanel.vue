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
        <div v-if="modelResultSummary" class="debug-result-card">
          <div class="debug-result-grid">
            <div class="debug-kv">
              <span>结果</span>
              <strong :class="modelResultSummary.ok ? 'ok' : 'bad'">{{ modelResultSummary.ok ? "通过" : "失败" }}</strong>
            </div>
            <div class="debug-kv">
              <span>后端</span>
              <strong>{{ modelResultSummary.backend }}</strong>
            </div>
            <div class="debug-kv">
              <span>模型</span>
              <strong>{{ modelResultSummary.modelId }}</strong>
            </div>
            <div class="debug-kv">
              <span>模式</span>
              <strong>{{ modelResultSummary.mode }}</strong>
            </div>
            <div class="debug-kv" v-if="modelResultSummary.device">
              <span>设备</span>
              <strong>{{ modelResultSummary.device }}</strong>
            </div>
            <div class="debug-kv" v-if="modelResultSummary.elapsedSec !== null">
              <span>耗时</span>
              <strong>{{ modelResultSummary.elapsedSec }}s</strong>
            </div>
            <div class="debug-kv" v-if="modelResultSummary.hashTotal > 0">
              <span>HASH校验</span>
              <strong>{{ modelResultSummary.hashPassed }}/{{ modelResultSummary.hashTotal }}</strong>
            </div>
          </div>
          <p class="notice" style="margin: 6px 0 0;">{{ modelResultSummary.message }}</p>
        </div>

        <div v-if="modelHashChecks.length" class="hash-table-wrap">
          <table class="hash-table">
            <thead>
              <tr>
                <th>文件</th>
                <th>算法</th>
                <th>状态</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in modelHashChecks" :key="`${item.file}-${idx}`">
                <td :title="item.file">{{ shortFile(item.file) }}</td>
                <td>{{ item.algorithm || "-" }}</td>
                <td>
                  <span :class="String(item.status || '').toLowerCase() === 'passed' ? 'chip-ok' : 'chip-bad'">
                    {{ String(item.status || '').toLowerCase() === 'passed' ? "通过" : "失败" }}
                  </span>
                </td>
                <td :title="item.message">
                  <span>{{ item.message || "-" }}</span>
                  <span v-if="item.expected || item.actual" class="hash-meta">
                    E:{{ shortHash(item.expected) }} / A:{{ shortHash(item.actual) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <details v-if="modelResult" class="raw-details">
          <summary>查看原始 JSON</summary>
          <pre class="mono" style="margin-top: 8px; white-space: pre-wrap;">{{ stringify(modelResult) }}</pre>
        </details>
      </div>

      <div class="param-section">
        <div class="param-title">测试翻译源</div>
        <p class="notice" style="margin-bottom: 10px;">支持 Ollama TCP-PING、模型列表检查、对话耗时评估，以及 OpenAI 兼容错误诊断。</p>
        <button type="button" :disabled="loadingTranslation" @click="onTestTranslation">
          {{ loadingTranslation ? "测试中..." : "测试翻译源" }}
        </button>
        <p v-if="translationError" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ translationError }}</p>

        <div v-if="translationResultSummary" class="debug-result-card">
          <div class="debug-result-grid">
            <div class="debug-kv">
              <span>结果</span>
              <strong :class="translationResultSummary.ok ? 'ok' : 'bad'">
                {{ translationResultSummary.ok ? "通过" : "失败" }}
              </strong>
            </div>
            <div class="debug-kv">
              <span>提供器</span>
              <strong>{{ translationResultSummary.provider }}</strong>
            </div>
            <div class="debug-kv" v-if="translationResultSummary.elapsedSec !== null">
              <span>耗时</span>
              <strong>{{ translationResultSummary.elapsedSec }}s</strong>
            </div>
            <div class="debug-kv" v-if="translationResultSummary.speedGrade">
              <span>速度评估</span>
              <strong>{{ translationResultSummary.speedGrade }}</strong>
            </div>
          </div>
          <p class="notice" style="margin: 6px 0 0;">{{ translationResultSummary.message }}</p>
          <p v-if="translationResultSummary.replyPreview" class="notice" style="margin: 4px 0 0;">
            回复预览：{{ translationResultSummary.replyPreview }}
          </p>
        </div>

        <div v-if="translationStepRows.length" class="hash-table-wrap">
          <table class="hash-table">
            <thead>
              <tr>
                <th>步骤</th>
                <th>状态</th>
                <th>耗时</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in translationStepRows" :key="`${item.step}-${idx}`">
                <td>{{ item.label }}</td>
                <td>
                  <span :class="item.status === 'passed' ? 'chip-ok' : 'chip-bad'">
                    {{ item.status === "passed" ? "通过" : "失败" }}
                  </span>
                </td>
                <td>{{ item.elapsedSec !== null ? `${item.elapsedSec}s` : "-" }}</td>
                <td>{{ item.message || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <details v-if="translationResult" class="raw-details">
          <summary>查看原始 JSON</summary>
          <pre class="mono" style="margin-top: 8px; white-space: pre-wrap;">{{ stringify(translationResult) }}</pre>
        </details>
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

const asObject = (value) => {
  if (!value || Array.isArray(value) || typeof value !== "object") return null;
  return value;
};

const modelResultSummary = computed(() => {
  const payload = asObject(props.modelResult);
  if (!payload) return null;
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  const hashStep = steps.find((item) => String(item?.name || "").toLowerCase() === "hash") || {};
  const warmupStep = steps.find((item) => String(item?.name || "").toLowerCase() === "warmup") || {};
  const hashChecks = Array.isArray(hashStep.checks) ? hashStep.checks : [];
  const hashPassed = hashChecks.filter((item) => String(item?.status || "").toLowerCase() === "passed").length;
  const hashTotal = hashChecks.length;
  return {
    ok: Boolean(payload.ok),
    backend: String(payload.backend || "-"),
    modelId: String(payload.model_id || "-"),
    mode: String(payload.mode || "-"),
    message: String(payload.message || payload.error || (payload.ok ? "执行成功" : "执行失败")),
    device: String(warmupStep.device || ""),
    elapsedSec: Number.isFinite(Number(warmupStep.elapsed_sec)) ? Number(warmupStep.elapsed_sec) : null,
    hashPassed,
    hashTotal,
  };
});

const modelHashChecks = computed(() => {
  const payload = asObject(props.modelResult);
  if (!payload) return [];
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  const hashStep = steps.find((item) => String(item?.name || "").toLowerCase() === "hash") || {};
  return Array.isArray(hashStep.checks) ? hashStep.checks : [];
});

const shortFile = (path) => {
  const safe = String(path || "").trim();
  if (!safe) return "-";
  const parts = safe.split("/");
  return parts[parts.length - 1] || safe;
};

const shortHash = (value) => {
  const safe = String(value || "").trim();
  if (!safe) return "-";
  if (safe.length <= 16) return safe;
  return `${safe.slice(0, 10)}...${safe.slice(-6)}`;
};

const _translationStepLabel = (name) => {
  const key = String(name || "").trim().toLowerCase();
  if (key === "tcp_ping") return "TCP 连通性";
  if (key === "list_models") return "模型列表";
  if (key === "chat") return "对话测试";
  return key || "-";
};

const translationStepRows = computed(() => {
  const payload = asObject(props.translationResult);
  if (!payload) return [];
  const steps = Array.isArray(payload.steps) ? payload.steps : [];
  return steps.map((item) => ({
    step: String(item.step || ""),
    label: _translationStepLabel(item.step),
    status: String(item.status || "").trim().toLowerCase() === "passed" ? "passed" : "failed",
    elapsedSec: Number.isFinite(Number(item.elapsed_sec)) ? Number(item.elapsed_sec) : null,
    message: String(item.message || item.speed_grade || item.reply_preview || ""),
  }));
});

const translationResultSummary = computed(() => {
  const payload = asObject(props.translationResult);
  if (!payload) return null;
  const steps = translationStepRows.value;
  const chatStep = (Array.isArray(payload.steps) ? payload.steps : []).find(
    (item) => String(item?.step || "").toLowerCase() === "chat"
  ) || {};
  const elapsedFromRoot = Number.isFinite(Number(payload.elapsed_sec)) ? Number(payload.elapsed_sec) : null;
  const elapsedFromChat = Number.isFinite(Number(chatStep.elapsed_sec)) ? Number(chatStep.elapsed_sec) : null;
  const speedGrade = String(chatStep.speed_grade || payload.speed_grade || "").trim();
  const replyPreview = String(chatStep.reply_preview || payload.reply_preview || "").trim();
  const message = String(payload.error || (payload.ok ? "翻译源测试通过" : "翻译源测试失败")).trim();
  const statusOk = Boolean(payload.ok);
  return {
    ok: statusOk,
    provider: String(payload.provider || "-"),
    elapsedSec: elapsedFromRoot ?? elapsedFromChat,
    speedGrade,
    replyPreview,
    message: message || (statusOk ? "翻译源测试通过" : "翻译源测试失败"),
    stepCount: steps.length,
  };
});

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

.debug-result-card {
  margin-top: 10px;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  padding: 10px;
  background: color-mix(in srgb, var(--panel-bg) 88%, transparent);
}

.debug-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
}

.debug-kv {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
}

.debug-kv span {
  opacity: 0.75;
}

.debug-kv strong.ok {
  color: #39b86f;
}

.debug-kv strong.bad {
  color: var(--accent-2);
}

.hash-table-wrap {
  margin-top: 10px;
  overflow-x: auto;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
}

.hash-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 640px;
  font-size: 12px;
}

.hash-table th,
.hash-table td {
  border-bottom: 1px solid var(--panel-border);
  text-align: left;
  vertical-align: top;
  padding: 6px 8px;
}

.hash-table tr:last-child td {
  border-bottom: none;
}

.chip-ok {
  color: #39b86f;
}

.chip-bad {
  color: var(--accent-2);
}

.hash-meta {
  display: block;
  margin-top: 2px;
  opacity: 0.75;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.raw-details {
  margin-top: 10px;
}
</style>
