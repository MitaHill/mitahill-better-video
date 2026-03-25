<template>
  <div class="param-section">
    <div class="param-title">转录基础</div>

    <div class="field">
      <label>上传音频或视频（可多选）</label>
      <input type="file" multiple accept="video/*,audio/*" @change="onTranscribeMediaChange" />
    </div>

    <div class="media-list" v-if="transcribeMediaInfo.length">
      <div class="media-row" v-for="item in transcribeMediaInfo" :key="item.filename + ':' + item.size_mb">
        <span>{{ item.filename }}</span>
        <span>{{ item.has_video ? "视频" : item.has_audio ? "音频" : "未知" }}</span>
        <span v-if="item.duration">{{ Math.round(item.duration) }}s</span>
        <span v-if="item.audio_sample_rate">{{ item.audio_sample_rate }} Hz</span>
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>转录类型</label>
        <select v-model="transcribeForm.transcribeMode" :disabled="isDisabled('transcribeMode')">
          <option v-for="item in transcribeModeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>字幕格式</label>
        <select v-model="transcribeForm.subtitleFormat" :disabled="isDisabled('subtitleFormat')">
          <option v-for="item in subtitleFormatOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>Fast-Whisper 模型</label>
        <select v-model="transcribeForm.whisperModel" :disabled="isDisabled('whisperModel')">
          <option v-for="model in whisperModelOptions" :key="model" :value="model">{{ model }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>语言</label>
        <select v-model="transcribeForm.language" :disabled="isDisabled('language')">
          <option v-for="item in languageOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>

    <div class="field compact">
      <label>翻译到</label>
      <select v-model="transcribeForm.translateTo" :disabled="isDisabled('translateTo')">
        <option value="">不翻译</option>
        <option v-for="item in translateTargetOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import {
  TRANSCRIPTION_LANGUAGE_CODES,
  TRANSCRIPTION_LANGUAGE_OPTIONS,
  TRANSCRIPTION_TARGET_LANGUAGE_CODES,
  TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS,
} from "../../../constants/transcriptionLanguages";

const props = defineProps({
  transcribeForm: {
    type: Object,
    required: true,
  },
  transcribeMediaInfo: {
    type: Array,
    required: true,
  },
  onTranscribeMediaChange: {
    type: Function,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const readPolicy = (fieldKey) => props.getFieldPolicy("transcribe", fieldKey) || null;
const isDisabled = (fieldKey) => Boolean(readPolicy(fieldKey)?.disabled);
const allowed = (fieldKey, fallback = []) => {
  const values = readPolicy(fieldKey)?.allowedValues;
  return Array.isArray(values) && values.length ? values : fallback;
};

const transcribeModeOptions = computed(() =>
  allowed("transcribeMode", ["subtitle_zip", "subtitled_video", "subtitle_and_video_zip"]).map((value) => ({
    value,
    label:
      value === "subtitle_zip"
        ? "字幕与文本（单文件直出 / 批量 ZIP）"
        : value === "subtitled_video"
          ? "生成带字幕视频（单视频直出 / 批量 ZIP）"
          : value === "subtitle_and_video_zip"
            ? "字幕与视频（统一 ZIP）"
            : value,
  }))
);

const subtitleFormatOptions = computed(() =>
  allowed("subtitleFormat", ["srt", "vtt"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);

const whisperModelOptions = computed(() =>
  allowed("whisperModel", ["small", "medium", "large-v3", "distil-large-v2", "distil-large-v3"])
);

const languageOptions = computed(() => {
  const constrained = allowed("language", TRANSCRIPTION_LANGUAGE_CODES);
  const constrainedSet = new Set(
    constrained.map((item) => String(item || "").trim().toLowerCase()).filter((item) => item.length > 0)
  );

  const base = TRANSCRIPTION_LANGUAGE_OPTIONS.filter((item) =>
    constrainedSet.has(String(item.value || "").trim().toLowerCase())
  );

  const seen = new Set(base.map((item) => String(item.value || "").trim().toLowerCase()));
  const extras = constrained
    .map((value) => String(value || "").trim())
    .filter((value) => value.length > 0 && !seen.has(value.toLowerCase()))
    .map((value) => ({ value, label: `${value} (${value})` }));
  return [...base, ...extras];
});

const translateTargetOptions = computed(() => {
  const constrained = allowed("translateTo", TRANSCRIPTION_TARGET_LANGUAGE_CODES);
  const constrainedSet = new Set(
    constrained.map((item) => String(item || "").trim().toLowerCase()).filter((item) => item.length > 0)
  );

  const base = TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS.filter((item) =>
    constrainedSet.has(String(item.value || "").trim().toLowerCase())
  );

  const seen = new Set(base.map((item) => String(item.value || "").trim().toLowerCase()));
  const extras = constrained
    .map((value) => String(value || "").trim())
    .filter((value) => value.length > 0 && !seen.has(value.toLowerCase()))
    .map((value) => ({ value, label: `${value} (${value})` }));

  return [...base, ...extras];
});
</script>
