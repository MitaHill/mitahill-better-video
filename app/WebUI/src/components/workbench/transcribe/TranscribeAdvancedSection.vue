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
    </div>
  </div>
</template>

<script setup>
import { useFieldPolicy } from "../../../composables/workbench/useFieldPolicy";

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

const { isDisabled, numMin, numMax, numStep } = useFieldPolicy(props.getFieldPolicy, "transcribe");

</script>
