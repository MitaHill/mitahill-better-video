<template>
  <div class="panel">
    <h2>{{ panelTitle }}</h2>

    <EnhanceTaskForm
      v-if="activeCategory === 'enhance'"
      :enhance-form="enhanceForm"
      :on-enhance-file-change="onEnhanceFileChange"
      :get-field-policy="getFieldPolicy"
    />

    <ConvertTaskForm
      v-else-if="activeCategory === 'convert'"
      :convert-form="convertForm"
      :convert-media-info="convertMediaInfo"
      :on-convert-media-change="onConvertMediaChange"
      :on-watermark-images-change="onWatermarkImagesChange"
      :on-watermark-lua-file-change="onWatermarkLuaFileChange"
      :add-watermark-segment="addWatermarkSegment"
      :remove-watermark-segment="removeWatermarkSegment"
      :get-field-policy="getFieldPolicy"
    />
    <TranscribeTaskForm
      v-else-if="activeCategory === 'transcribe'"
      :transcribe-form="transcribeForm"
      :transcribe-media-info="transcribeMediaInfo"
      :on-transcribe-media-change="onTranscribeMediaChange"
      :get-field-policy="getFieldPolicy"
    />
    <DownloadTaskForm v-else :download-form="downloadForm" :on-probe-source="onProbeDownloadSource" />

    <div class="action-row">
      <button @click="submitTask" :disabled="loadingSubmit">
        {{ loadingSubmit ? '提交中...' : submitText }}
      </button>
    </div>

    <p v-if="submitError" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ submitError }}</p>
    <p v-if="submitWarnings" class="notice" style="margin-top: 8px;">{{ submitWarnings }}</p>
  </div>
</template>

<script setup>
import ConvertTaskForm from "./ConvertTaskForm.vue";
import DownloadTaskForm from "./DownloadTaskForm.vue";
import EnhanceTaskForm from "./EnhanceTaskForm.vue";
import TranscribeTaskForm from "./TranscribeTaskForm.vue";
import { computed } from "vue";

const props = defineProps({
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
  transcribeForm: {
    type: Object,
    required: true,
  },
  transcribeMediaInfo: {
    type: Array,
    required: true,
  },
  downloadForm: {
    type: Object,
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
  onTranscribeMediaChange: {
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
  onProbeDownloadSource: {
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
  getFieldPolicy: {
    type: Function,
    required: true,
  },
  submitTask: {
    type: Function,
    required: true,
  },
});

const panelTitle = computed(() => {
  if (props.activeCategory === "convert") return "创建转换任务";
  if (props.activeCategory === "transcribe") return "创建转录任务";
  if (props.activeCategory === "download") return "创建下载任务";
  return "创建增强任务";
});

const submitText = computed(() => {
  if (props.activeCategory === "convert") return "转换任务开始";
  if (props.activeCategory === "transcribe") return "转录任务开始";
  if (props.activeCategory === "download") return "下载任务开始";
  return "增强任务开始";
});
</script>
