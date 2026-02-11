<template>
  <div class="param-section">
    <div class="param-title">任务基础</div>
    <div class="field">
      <label>输入类型</label>
      <select v-model="enhanceForm.inputType" :disabled="isDisabled('inputType')">
        <option v-for="item in inputTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="field">
      <label>上传文件（支持批量）</label>
      <input type="file" multiple @change="onEnhanceFileChange" />
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
  onEnhanceFileChange: {
    type: Function,
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

const inputTypeOptions = computed(() =>
  allowed("inputType", ["Video", "Image"]).map((value) => ({
    value,
    label: value === "Video" ? "视频" : value === "Image" ? "图片" : value,
  }))
);
</script>
