<template>
  <div class="param-section">
    <div class="param-title">任务基础</div>
    <div class="field">
      <label>转换类型</label>
      <select v-model="convertForm.convertMode" :disabled="isDisabled('convertMode')">
        <option v-for="item in convertModeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="field">
      <label>上传音频或视频（可多选）</label>
      <input type="file" multiple accept="video/*,audio/*" @change="onConvertMediaChange" />
    </div>
    <div class="media-list" v-if="convertMediaInfo.length">
      <div class="media-row" v-for="item in convertMediaInfo" :key="item.filename + ':' + item.size_mb">
        <span>{{ item.filename }}</span>
        <span>{{ item.has_video ? '视频' : (item.has_audio ? '音频' : '未知') }}</span>
        <span v-if="item.fps">{{ item.fps }} fps</span>
        <span v-if="item.video_codec">{{ item.video_codec.toUpperCase() }}</span>
        <span v-if="item.audio_sample_rate">{{ item.audio_sample_rate }} Hz</span>
        <span v-if="item.audio_bitrate">{{ Math.round(item.audio_bitrate / 1000) }} kbps</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  convertMediaInfo: {
    type: Array,
    required: true,
  },
  onConvertMediaChange: {
    type: Function,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const readPolicy = (fieldKey) => props.getFieldPolicy("convert", fieldKey) || null;
const isDisabled = (fieldKey) => Boolean(readPolicy(fieldKey)?.disabled);
const allowed = (fieldKey, fallback = []) => {
  const values = readPolicy(fieldKey)?.allowedValues;
  return Array.isArray(values) && values.length ? values : fallback;
};

const convertModeOptions = computed(() =>
  allowed("convertMode", ["transcode", "export_frames", "demux_streams"]).map((value) => ({
    value,
    label:
      value === "transcode"
        ? "视频转换"
        : value === "export_frames"
          ? "导出视频帧（批量 ZIP）"
          : value === "demux_streams"
            ? "分离画面流和音频流（批量 ZIP）"
            : value,
  }))
);
</script>
