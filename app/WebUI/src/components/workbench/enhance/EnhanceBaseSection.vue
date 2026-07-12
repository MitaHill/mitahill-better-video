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
      <div class="file-picker-row">
        <button type="button" class="secondary" @click="openFilePicker">
          {{ selectedFileCount ? "重新选择文件" : "选择文件" }}
        </button>
        <span v-if="selectedFileCount" class="selected-file-count">已选择 {{ selectedFileCount }} 个文件</span>
      </div>
      <div class="media-list" v-if="selectedFiles.length">
        <div class="media-row" v-for="file in selectedFiles" :key="file.name + ':' + file.size">
          <span>{{ file.name }}</span>
        </div>
      </div>
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

const selectedFiles = computed(() => (Array.isArray(props.enhanceForm?.files) ? props.enhanceForm.files : []));
const selectedFileCount = computed(() => selectedFiles.value.length);

const inputTypeOptions = computed(() =>
  allowed("inputType", ["Video", "Image"]).map((value) => ({
    value,
    label: value === "Video" ? "视频" : value === "Image" ? "图片" : value,
  }))
);
</script>
