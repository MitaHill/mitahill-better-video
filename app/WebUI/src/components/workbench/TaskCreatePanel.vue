<template>
  <div class="panel">
    <h2>{{ activeCategory === 'enhance' ? '创建增强任务' : '创建转换任务' }}</h2>

    <EnhanceTaskForm
      v-if="activeCategory === 'enhance'"
      :enhance-form="enhanceForm"
      :on-enhance-file-change="onEnhanceFileChange"
    />

    <ConvertTaskForm
      v-else
      :convert-form="convertForm"
      :convert-media-info="convertMediaInfo"
      :on-convert-media-change="onConvertMediaChange"
      :on-watermark-images-change="onWatermarkImagesChange"
      :on-watermark-lua-file-change="onWatermarkLuaFileChange"
      :add-watermark-segment="addWatermarkSegment"
      :remove-watermark-segment="removeWatermarkSegment"
    />

    <div class="action-row">
      <button @click="submitTask" :disabled="loadingSubmit">
        {{ loadingSubmit ? '提交中...' : (activeCategory === 'convert' ? '转换任务开始' : '增强任务开始') }}
      </button>
    </div>

    <p v-if="submitError" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ submitError }}</p>
    <p v-if="submitWarnings" class="notice" style="margin-top: 8px;">{{ submitWarnings }}</p>
  </div>
</template>

<script setup>
import ConvertTaskForm from "./ConvertTaskForm.vue";
import EnhanceTaskForm from "./EnhanceTaskForm.vue";

defineProps({
  activeCategory: {
    type: String,
    required: true,
  },
  enhanceForm: {
    type: Object,
    required: true,
  },
  convertForm: {
    type: Object,
    required: true,
  },
  convertMediaInfo: {
    type: Array,
    required: true,
  },
  loadingSubmit: {
    type: Boolean,
    required: true,
  },
  submitError: {
    type: String,
    required: true,
  },
  submitWarnings: {
    type: String,
    required: true,
  },
  onEnhanceFileChange: {
    type: Function,
    required: true,
  },
  onConvertMediaChange: {
    type: Function,
    required: true,
  },
  onWatermarkImagesChange: {
    type: Function,
    required: true,
  },
  onWatermarkLuaFileChange: {
    type: Function,
    required: true,
  },
  addWatermarkSegment: {
    type: Function,
    required: true,
  },
  removeWatermarkSegment: {
    type: Function,
    required: true,
  },
  submitTask: {
    type: Function,
    required: true,
  },
});
</script>
