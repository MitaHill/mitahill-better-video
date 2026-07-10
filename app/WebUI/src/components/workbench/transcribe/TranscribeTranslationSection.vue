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

const runtimeTranslation = computed(() => props.runtimeConfig?.translation || null);

const runtimeSummary = computed(() => {
  const translation = runtimeTranslation.value;
  if (!translation || !translation.provider || translation.provider === "none") {
    return "后台未启用默认翻译源";
  }
  const model = String(translation.model || "").trim() || "未配置模型";
  const baseUrl = String(translation.base_url || "").trim() || "未配置地址";
  return `OpenAI 兼容 / ${model} / ${baseUrl}`;
});

const translationModeLabel = computed(() => {
  if (!props.transcribeForm.translateTo) return "不翻译";
  return "OpenAI 兼容";
});

const translationModeDescription = computed(() => {
  if (!props.transcribeForm.translateTo) {
    return "当前未选择目标语言，本次任务只做转录，不会进入翻译阶段。";
  }
  return "当前任务会使用后台管理页面配置的 OpenAI 兼容翻译源。";
});

const showDisableTranslationButton = computed(() => Boolean(props.transcribeForm.translateTo));

const disableTranslation = () => {
  props.transcribeForm.translateTo = "";
  props.transcribeForm.translatorProvider = "none";
};
</script>
