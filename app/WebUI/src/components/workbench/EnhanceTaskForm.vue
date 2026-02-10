<template>
  <div class="param-group">
    <EnhanceBaseSection :enhance-form="enhanceForm" :on-enhance-file-change="onEnhanceFileChange" />
    <EnhanceVisualSection :enhance-form="enhanceForm" />
    <EnhanceAudioSection :enhance-form="enhanceForm" />
    <EnhanceEncodeSection :enhance-form="enhanceForm" />
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
});
</script>
