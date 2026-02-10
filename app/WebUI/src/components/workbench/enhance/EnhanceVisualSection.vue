<template>
  <div class="param-section">
    <div class="param-title">画面参数</div>
    <div class="field">
      <label>模型</label>
      <select v-model="enhanceForm.modelName" :disabled="isDisabled('modelName')">
        <option v-for="item in modelOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="field">
      <label>放大倍率：{{ enhanceForm.upscale }}x</label>
      <input
        v-model.number="enhanceForm.upscale"
        type="range"
        :min="numMin('upscale', 2)"
        :max="numMax('upscale', 4)"
        :step="numStep('upscale', 1)"
        :disabled="isDisabled('upscale')"
      />
    </div>
    <div class="field">
      <label>切片大小：{{ enhanceForm.tile }}</label>
      <input
        v-model.number="enhanceForm.tile"
        type="range"
        :min="numMin('tile', 64)"
        :max="numMax('tile', 512)"
        :step="numStep('tile', 64)"
        :disabled="isDisabled('tile')"
      />
    </div>
    <div class="field" v-if="enhanceForm.modelName.includes('general')">
      <label>降噪强度：{{ enhanceForm.denoise.toFixed(2) }}</label>
      <input
        v-model.number="enhanceForm.denoise"
        type="range"
        :min="numMin('denoise', 0)"
        :max="numMax('denoise', 1)"
        :step="numStep('denoise', 0.05)"
        :disabled="isDisabled('denoise')"
      />
    </div>
    <div class="field" v-if="enhanceForm.inputType === 'Video'">
      <label>反交错</label>
      <select v-model="enhanceForm.deinterlace" :disabled="isDisabled('deinterlace')">
        <option :value="false">关闭</option>
        <option :value="true">启用</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  enhanceForm: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const MODEL_LABELS = Object.freeze({
  "realesrgan-x4plus": "通用（高清）",
  "realesrnet-x4plus": "降噪（慢速）",
  "realesrgan-x4plus-anime": "二次元",
  "realesr-animevideov3": "二次元视频（快）",
  "realesr-general-x4v3": "通用（快速）",
});

const readPolicy = (fieldKey) => props.getFieldPolicy("enhance", fieldKey) || null;
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

const modelOptions = computed(() =>
  allowed("modelName", Object.keys(MODEL_LABELS)).map((value) => ({
    value,
    label: MODEL_LABELS[value] || value,
  }))
);
</script>
