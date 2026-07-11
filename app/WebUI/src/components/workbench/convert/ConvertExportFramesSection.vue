<template>
  <div class="param-section" v-if="convertForm.convertMode === 'export_frames'">
    <div class="param-title">导出帧参数</div>
    <div class="inline-grid two">
      <div class="field compact">
        <label>导出帧率模式</label>
        <select v-model="convertForm.frameExportFpsMode" :disabled="isDisabled('frameExportFpsMode')">
          <option v-for="item in fpsModeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>导出图片格式</label>
        <select v-model="convertForm.frameExportFormat" :disabled="isDisabled('frameExportFormat')">
          <option v-for="item in frameFormatOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>
    <div class="field compact">
      <label>导出帧率（fps）</label>
      <input
        v-model.number="convertForm.frameExportFps"
        type="number"
        :min="numMin('frameExportFps', 0)"
        :max="numMax('frameExportFps', 120)"
        :step="numStep('frameExportFps', 1)"
        :disabled="convertForm.frameExportFpsMode === 'auto' || isDisabled('frameExportFps')"
        placeholder="0=导出全部帧"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useFieldPolicy } from "../../../composables/workbench/useFieldPolicy";

const props = defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const { isDisabled, allowed, numMin, numMax, numStep } = useFieldPolicy(props.getFieldPolicy, "convert");

const fpsModeOptions = computed(() =>
  allowed("frameExportFpsMode", ["manual", "auto"]).map((value) => ({
    value,
    label: value === "auto" ? "自动适应源帧率" : "手动",
  }))
);

const frameFormatOptions = computed(() =>
  allowed("frameExportFormat", ["jpg", "jpeg", "png", "gif", "pdf"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);
</script>
