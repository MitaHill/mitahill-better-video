<template>
  <div class="param-section">
    <div class="param-title">转录参数</div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>温度</label>
        <input
          v-model.number="transcribeForm.temperature"
          type="number"
          :step="numStep('temperature', 0.1)"
          :min="numMin('temperature', 0)"
          :max="numMax('temperature', 1)"
          :disabled="isDisabled('temperature')"
        />
      </div>
      <div class="field compact">
        <label>Beam Size</label>
        <input
          v-model.number="transcribeForm.beamSize"
          type="number"
          :min="numMin('beamSize', 1)"
          :max="numMax('beamSize', 20)"
          :step="numStep('beamSize', 1)"
          :disabled="isDisabled('beamSize')"
        />
      </div>
      <div class="field compact">
        <label>Best Of</label>
        <input
          v-model.number="transcribeForm.bestOf"
          type="number"
          :min="numMin('bestOf', 1)"
          :max="numMax('bestOf', 20)"
          :step="numStep('bestOf', 1)"
          :disabled="isDisabled('bestOf')"
        />
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>最大行宽</label>
        <input
          v-model.number="transcribeForm.maxLineChars"
          type="number"
          :min="numMin('maxLineChars', 0)"
          :max="numMax('maxLineChars', 200)"
          :step="numStep('maxLineChars', 1)"
          :disabled="isDisabled('maxLineChars')"
        />
      </div>
      <div class="field compact">
        <label>输出音频码率 (k)</label>
        <input
          v-model.number="transcribeForm.outputAudioBitrateK"
          type="number"
          :min="numMin('outputAudioBitrateK', 32)"
          :max="numMax('outputAudioBitrateK', 1024)"
          :step="numStep('outputAudioBitrateK', 1)"
          :disabled="isDisabled('outputAudioBitrateK')"
        />
      </div>
    </div>

    <div class="inline-grid two">
      <label class="check-inline">
        <input v-model="transcribeForm.prependTimestamps" type="checkbox" :disabled="isDisabled('prependTimestamps')" />
        文本附带时间戳
      </label>
      <div class="field compact" v-if="transcribeForm.transcribeMode === 'subtitled_video'">
        <label>视频编码</label>
        <select v-model="transcribeForm.outputVideoCodec" :disabled="isDisabled('outputVideoCodec')">
          <option v-for="item in outputVideoCodecOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>翻译超时(秒)</label>
        <input
          v-model.number="transcribeForm.translatorTimeoutSec"
          type="number"
          :min="numMin('translatorTimeoutSec', 1)"
          :max="numMax('translatorTimeoutSec', 1200)"
          :step="numStep('translatorTimeoutSec', 1)"
          :disabled="isDisabled('translatorTimeoutSec')"
        />
      </div>
      <label class="check-inline">
        <input v-model="transcribeForm.generateBilingual" type="checkbox" :disabled="isDisabled('generateBilingual')" />
        生成双语字幕
      </label>
    </div>

    <p class="notice" style="margin-top: 4px;">
      翻译提供器与翻译模型由后端管理页面统一配置，用户端任务创建不提供手动切换。
    </p>
    <p v-if="transcribeRuntime.loading" class="notice">正在读取后台翻译源配置...</p>
    <p v-else-if="transcribeRuntime.error" class="notice" style="color: var(--accent-2);">
      后台翻译源读取失败：{{ transcribeRuntime.error }}
    </p>
    <p v-else class="notice">
      当前后台翻译源（只读）：{{ translatorProviderLabel }} / {{ transcribeRuntime.translation?.model || "-" }}
      （{{ transcribeRuntime.translation?.enabled ? "可用" : "未就绪" }}，模式:
      {{ translatorModeLabel }}，上下文窗:
      {{ transcribeRuntime.translation?.context_window_size || "-" }}，批次窗:
      {{ transcribeRuntime.translation?.batch_window_size || "-" }}）
    </p>

    <label class="check-inline">
      <input v-model="transcribeForm.exportJson" type="checkbox" :disabled="isDisabled('exportJson')" />
      导出 JSON 分段
    </label>

  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  transcribeForm: {
    type: Object,
    required: true,
  },
  transcribeRuntime: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const readPolicy = (fieldKey) => props.getFieldPolicy("transcribe", fieldKey) || null;
const isDisabled = (fieldKey) => Boolean(readPolicy(fieldKey)?.disabled);
const allowed = (fieldKey, fallback = []) => {
  const values = readPolicy(fieldKey)?.allowedValues;
  return Array.isArray(values) && values.length ? values : fallback;
};

const toFiniteOr = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const numMin = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.minValue, fallback);
const numMax = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.maxValue, fallback);
const numStep = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.step, fallback);

const outputVideoCodecOptions = computed(() =>
  allowed("outputVideoCodec", ["h264", "h265"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);

const translatorProviderLabel = computed(() => {
  const provider = String(props.transcribeRuntime?.translation?.provider || "none").trim().toLowerCase();
  if (provider === "ollama") return "Ollama";
  if (provider === "openai_compatible") return "OpenAI兼容";
  return "不启用";
});

const translatorModeLabel = computed(() => {
  const mode = String(props.transcribeRuntime?.translation?.mode || "window_batch").trim().toLowerCase();
  if (mode === "single_sentence") return "单句翻译";
  return "滑动窗口";
});
</script>
