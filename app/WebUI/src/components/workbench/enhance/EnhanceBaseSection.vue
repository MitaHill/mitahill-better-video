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
      <input ref="fileInput" class="file-input-hidden" type="file" multiple @change="onEnhanceFileChange" />
      <button type="button" class="secondary" @click="openFilePicker">选择文件</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useFieldPolicy } from "../../../composables/workbench/useFieldPolicy";

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

const { isDisabled, allowed } = useFieldPolicy(props.getFieldPolicy, "enhance");
const fileInput = ref(null);

const openFilePicker = () => {
  fileInput.value?.click();
};

const inputTypeOptions = computed(() =>
  allowed("inputType", ["Video", "Image"]).map((value) => ({
    value,
    label: value === "Video" ? "视频" : value === "Image" ? "图片" : value,
  }))
);
</script>
