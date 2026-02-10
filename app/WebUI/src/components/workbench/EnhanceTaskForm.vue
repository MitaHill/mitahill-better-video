<template>
  <div class="param-group">
    <EnhanceBaseSection :enhance-form="enhanceForm" :on-enhance-file-change="onEnhanceFileChange" :get-field-policy="getFieldPolicy" />
    <EnhanceVisualSection :enhance-form="enhanceForm" :get-field-policy="getFieldPolicy" />
    <EnhanceAudioSection :enhance-form="enhanceForm" :get-field-policy="getFieldPolicy" />
    <EnhanceEncodeSection :enhance-form="enhanceForm" :get-field-policy="getFieldPolicy" />
  </div>
</template>

<script setup>
import EnhanceAudioSection from "./enhance/EnhanceAudioSection.vue";
import EnhanceBaseSection from "./enhance/EnhanceBaseSection.vue";
import EnhanceEncodeSection from "./enhance/EnhanceEncodeSection.vue";
import EnhanceVisualSection from "./enhance/EnhanceVisualSection.vue";

defineProps({
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
</script>
