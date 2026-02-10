<template>
  <div class="param-section" v-if="enhanceForm.inputType === 'Video'">
    <div class="param-title">编码参数</div>
    <div class="field">
      <label>输出编码</label>
      <select v-model="enhanceForm.outputCodec" :disabled="isDisabled('outputCodec')">
        <option v-for="item in codecOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="field">
      <label>CRF 质量：{{ enhanceForm.crf }}</label>
      <input
        v-model.number="enhanceForm.crf"
        type="range"
        :min="numMin('crf', 10)"
        :max="numMax('crf', 30)"
        :step="numStep('crf', 1)"
        :disabled="isDisabled('crf')"
      />
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

const codecOptions = computed(() =>
  allowed("outputCodec", ["h264", "h265"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);
</script>
