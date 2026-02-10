<template>
  <div class="param-section" v-if="enhanceForm.inputType === 'Video'">
    <div class="param-title">音频参数</div>
    <div class="field">
      <label>保留原音轨</label>
      <select v-model="enhanceForm.keepAudio">
        <option :value="true">是</option>
        <option :value="false">否</option>
      </select>
    </div>
    <div class="field">
      <label>音频增强</label>
      <select v-model="enhanceForm.audioEnhance">
        <option :value="true">启用</option>
        <option :value="false">关闭</option>
      </select>
    </div>
    <div class="field">
      <label>前置降噪</label>
      <select v-model="enhanceForm.preDenoiseMode">
        <option value="off">关闭</option>
        <option value="speech_enhance">人声增强 (DeepFilterNet2)</option>
        <option value="vhs_hiss">VHS 嘶声降噪</option>
      </select>
    </div>
    <div class="field">
      <label>哈斯效应</label>
      <label class="check-inline"><input type="checkbox" v-model="enhanceForm.haasEnabled" />启用</label>
      <div class="inline-grid two">
        <input v-model.number="enhanceForm.haasDelayMs" type="number" min="0" max="3000" step="1" :disabled="!enhanceForm.haasEnabled" placeholder="延迟 ms" />
        <select v-model="enhanceForm.haasLead" :disabled="!enhanceForm.haasEnabled">
          <option value="left">左声道先出声</option>
          <option value="right">右声道先出声</option>
        </select>
      </div>
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
