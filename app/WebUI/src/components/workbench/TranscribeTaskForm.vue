<template>
  <div class="param-group">
    <TranscribeBaseSection
      :transcribe-form="transcribeForm"
      :transcribe-media-info="transcribeMediaInfo"
      :on-transcribe-media-change="onTranscribeMediaChange"
      :get-field-policy="getFieldPolicy"
    />
    <TranscribeAdvancedSection :transcribe-form="transcribeForm" :get-field-policy="getFieldPolicy" />
  </div>
</template>

<script setup>
import TranscribeAdvancedSection from "./transcribe/TranscribeAdvancedSection.vue";
import TranscribeBaseSection from "./transcribe/TranscribeBaseSection.vue";

defineProps({
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
</script>
