<template>
  <div class="param-section" v-if="enhanceForm.inputType === 'Video'">
    <div class="param-title">音频参数</div>
    <div class="field">
      <label>保留原音轨</label>
      <select v-model="enhanceForm.keepAudio" :disabled="isDisabled('keepAudio')">
        <option :value="true">是</option>
        <option :value="false">否</option>
      </select>
    </div>
    <div class="field">
      <label>音频增强</label>
      <select v-model="enhanceForm.audioEnhance" :disabled="isDisabled('audioEnhance')">
        <option :value="true">启用</option>
        <option :value="false">关闭</option>
      </select>
    </div>
    <div class="field">
      <label>前置降噪</label>
      <select v-model="enhanceForm.preDenoiseMode" :disabled="isDisabled('preDenoiseMode')">
        <option v-for="item in preDenoiseOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="field">
      <label>哈斯效应</label>
      <label class="check-inline"><input type="checkbox" v-model="enhanceForm.haasEnabled" :disabled="isDisabled('haasEnabled')" />启用</label>
      <div class="inline-grid two">
        <input
          v-model.number="enhanceForm.haasDelayMs"
          type="number"
          :min="numMin('haasDelayMs', 0)"
          :max="numMax('haasDelayMs', 3000)"
          :step="numStep('haasDelayMs', 1)"
          :disabled="!enhanceForm.haasEnabled || isDisabled('haasDelayMs')"
          placeholder="延迟 ms"
        />
        <select v-model="enhanceForm.haasLead" :disabled="!enhanceForm.haasEnabled || isDisabled('haasLead')">
          <option v-for="item in haasLeadOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
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

const preDenoiseOptions = computed(() =>
  allowed("preDenoiseMode", ["off", "speech_enhance", "vhs_hiss"]).map((value) => ({
    value,
    label: value === "off" ? "关闭" : value === "speech_enhance" ? "人声增强 (DeepFilterNet2)" : value === "vhs_hiss" ? "VHS 嘶声降噪" : value,
  }))
);

const haasLeadOptions = computed(() =>
  allowed("haasLead", ["left", "right"]).map((value) => ({
    value,
    label: value === "left" ? "左声道先出声" : value === "right" ? "右声道先出声" : value,
  }))
);
</script>
