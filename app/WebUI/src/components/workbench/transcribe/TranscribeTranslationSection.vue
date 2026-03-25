<template>
  <div class="param-section">
    <div class="param-title">翻译策略</div>

    <div class="transcribe-note-card">
      <div class="transcribe-note-head">
        <strong>本次任务的翻译行为</strong>
        <span class="transcribe-note-tag">{{ translationModeLabel }}</span>
      </div>
      <p class="notice">{{ translationModeDescription }}</p>
      <p class="notice" v-if="runtimeSummary">后台当前默认：{{ runtimeSummary }}</p>
      <div class="status-row" style="gap: 8px; margin-top: 10px;">
        <button
          v-if="showApplyRuntimeButton"
          type="button"
          class="secondary"
          @click="applyRuntimeDefaults"
        >
          套用后台默认翻译源
        </button>
        <button
          v-if="showDisableTranslationButton"
          type="button"
          class="secondary"
          @click="disableTranslation"
        >
          本次任务不翻译
        </button>
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>翻译到</label>
        <select v-model="transcribeForm.translateTo" :disabled="isDisabled('translateTo')">
          <option value="">不翻译</option>
          <option v-for="item in translateTargetOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>翻译提供器</label>
        <select v-model="transcribeForm.translatorProvider" :disabled="isDisabled('translatorProvider') || !transcribeForm.translateTo">
          <option v-for="item in translatorProviderOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>

    <div v-if="transcribeForm.translateTo" class="inline-grid two">
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
      <label class="check-inline transcribe-check-card">
        <input v-model="transcribeForm.generateBilingual" type="checkbox" :disabled="isDisabled('generateBilingual')" />
        生成双语字幕
      </label>
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="inline-grid two">
      <div class="field compact">
        <label>翻译服务地址</label>
        <input
          v-model="transcribeForm.translatorBaseUrl"
          :placeholder="transcribeForm.translatorProvider === 'openai' ? '留空则使用 https://api.openai.com/v1' : 'http://127.0.0.1:11434 或 https://api.xxx/v1'"
          :disabled="isDisabled('translatorBaseUrl')"
        />
      </div>
      <div class="field compact">
        <label>翻译模型名</label>
        <input
          v-model="transcribeForm.translatorModel"
          placeholder="qwen3:8b / gpt-4.1"
          :disabled="isDisabled('translatorModel')"
        />
      </div>
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译 API Key</label>
      <input
        v-model="transcribeForm.translatorApiKey"
        type="password"
        :placeholder="transcribeForm.translatorProvider === 'openai' ? 'OpenAI 云端为必填' : '留空则不带 Authorization 头'"
        :disabled="isDisabled('translatorApiKey')"
      />
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译提示词（可选）</label>
      <textarea
        v-model="transcribeForm.translatorPrompt"
        rows="4"
        placeholder="留空使用后端默认提示词"
        :disabled="isDisabled('translatorPrompt')"
      ></textarea>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { TRANSCRIPTION_TARGET_LANGUAGE_CODES, TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS } from "../../../constants/transcriptionLanguages";

const props = defineProps({
  transcribeForm: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
  runtimeConfig: {
    type: Object,
    default: null,
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

const translateTargetOptions = computed(() => {
  const constrained = allowed("translateTo", TRANSCRIPTION_TARGET_LANGUAGE_CODES);
  const constrainedSet = new Set(
    constrained.map((item) => String(item || "").trim().toLowerCase()).filter((item) => item.length > 0)
  );
  return TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS.filter((item) =>
    constrainedSet.has(String(item.value || "").trim().toLowerCase())
  );
});

const translatorProviderOptions = computed(() =>
  allowed("translatorProvider", ["none", "ollama", "openai", "openai_compatible"]).map((value) => ({
    value,
    label:
      value === "none"
        ? "不启用（不翻译）"
        : value === "ollama"
          ? "Ollama"
          : value === "openai"
            ? "OpenAI 云端"
            : value === "openai_compatible"
              ? "OpenAI 兼容"
              : value,
  }))
);

const runtimeTranslation = computed(() => props.runtimeConfig?.translation || null);

const runtimeSummary = computed(() => {
  const translation = runtimeTranslation.value;
  if (!translation || !translation.provider || translation.provider === "none") {
    return "后台未启用默认翻译源";
  }
  const model = String(translation.model || "").trim() || "未配置模型";
  const baseUrl = String(translation.base_url || "").trim() || "未配置地址";
  const providerLabel =
    translation.provider === "openai"
      ? "OpenAI 云端"
      : translation.provider === "openai_compatible"
        ? "OpenAI 兼容"
        : translation.provider === "ollama"
          ? "Ollama"
          : translation.provider;
  return `${providerLabel} / ${model} / ${baseUrl}`;
});

const translationModeLabel = computed(() => {
  if (!props.transcribeForm.translateTo) return "不翻译";
  if (props.transcribeForm.translatorProvider === "none") return "翻译已关闭";
  return "使用本次任务设置";
});

const translationModeDescription = computed(() => {
  if (!props.transcribeForm.translateTo) {
    return "当前未选择目标语言，本次任务只做转录，不会进入翻译阶段。";
  }
  if (props.transcribeForm.translatorProvider === "none") {
    return "当前“翻译提供器”设为“不启用”，表示本次任务不翻译，也不会自动继承后台默认翻译源。";
  }
  return "当前任务会严格按这里填写的翻译源执行；如果你想快速沿用后台默认翻译配置，可以直接点“套用后台默认翻译源”。";
});

const showApplyRuntimeButton = computed(() => {
  const translation = runtimeTranslation.value;
  return Boolean(props.transcribeForm.translateTo) && translation && translation.provider && translation.provider !== "none";
});

const showDisableTranslationButton = computed(() => Boolean(props.transcribeForm.translateTo));

const applyRuntimeDefaults = () => {
  const translation = runtimeTranslation.value;
  if (!translation) return;
  props.transcribeForm.translatorProvider = String(translation.provider || "none");
  props.transcribeForm.translatorBaseUrl = String(translation.base_url || "");
  props.transcribeForm.translatorModel = String(translation.model || "");
};

const disableTranslation = () => {
  props.transcribeForm.translateTo = "";
  props.transcribeForm.translatorProvider = "none";
};
</script>
