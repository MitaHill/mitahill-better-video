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
      <label class="check-inline">
        <input v-model="transcribeForm.prependTimestamps" type="checkbox" :disabled="isDisabled('prependTimestamps')" />
        文本附带时间戳
      </label>
    </div>

    <div class="inline-grid two">
      <label class="check-inline">
        <input v-model="transcribeForm.generateBilingual" type="checkbox" :disabled="isDisabled('generateBilingual')" />
        生成双语字幕
      </label>
    </div>

    <label class="check-inline">
      <input v-model="transcribeForm.exportJson" type="checkbox" :disabled="isDisabled('exportJson')" />
      导出 JSON 分段
    </label>
  </div>
</template>

<script setup>
const props = defineProps({
  transcribeForm: {
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
const toFiniteOr = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const numMin = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.minValue, fallback);
const numMax = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.maxValue, fallback);
const numStep = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.step, fallback);

</script>
