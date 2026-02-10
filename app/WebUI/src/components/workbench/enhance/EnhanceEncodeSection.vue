<template>
  <div class="param-section" v-if="enhanceForm.inputType === 'Video'">
    <div class="param-title">编码参数</div>
    <div class="field">
      <label>输出编码</label>
      <select v-model="enhanceForm.outputCodec">
        <option value="h264">H264</option>
        <option value="h265">H265</option>
      </select>
    </div>
    <div class="field">
      <label>CRF 质量：{{ enhanceForm.crf }}</label>
      <input v-model.number="enhanceForm.crf" type="range" min="10" max="30" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  enhanceForm: {
    type: Object,
    required: true,
  },
});
</script>
