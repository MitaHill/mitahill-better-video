<template>
  <div class="param-section" v-if="enhanceForm.inputType === 'Video'">
    <div class="param-title">编码参数</div>
    <div class="field">
      <label>输出编码</label>
      <select v-model="enhanceForm.outputCodec" :disabled="isDisabled('outputCodec') || codecOptions.length === 0">
        <option v-if="codecOptions.length === 0" value="">无可用 GPU 编码器</option>
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
import { useFieldPolicy } from "../../../composables/workbench/useFieldPolicy";

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

const { isDisabled, allowed, numMin, numMax, numStep } = useFieldPolicy(props.getFieldPolicy, "enhance");

const codecOptions = computed(() =>
  allowed("outputCodec", props.enhanceForm.outputCodecOptions || []).map((value) => ({
    value,
    label: value === "h265" ? "H.265/HEVC" : value === "av1" ? "AV1" : String(value || "").toUpperCase(),
  }))
);
</script>
