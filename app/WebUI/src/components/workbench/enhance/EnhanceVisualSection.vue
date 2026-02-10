<template>
  <div class="param-section">
    <div class="param-title">画面参数</div>
    <div class="field">
      <label>模型</label>
      <select v-model="enhanceForm.modelName">
        <option value="realesrgan-x4plus">通用（高清）</option>
        <option value="realesrnet-x4plus">降噪（慢速）</option>
        <option value="realesrgan-x4plus-anime">二次元</option>
        <option value="realesr-animevideov3">二次元视频（快）</option>
        <option value="realesr-general-x4v3">通用（快速）</option>
      </select>
    </div>
    <div class="field">
      <label>放大倍率：{{ enhanceForm.upscale }}x</label>
      <input v-model.number="enhanceForm.upscale" type="range" min="2" max="4" step="1" />
    </div>
    <div class="field">
      <label>切片大小：{{ enhanceForm.tile }}</label>
      <input v-model.number="enhanceForm.tile" type="range" min="64" max="512" step="64" />
    </div>
    <div class="field" v-if="enhanceForm.modelName.includes('general')">
      <label>降噪强度：{{ enhanceForm.denoise.toFixed(2) }}</label>
      <input v-model.number="enhanceForm.denoise" type="range" min="0" max="1" step="0.05" />
    </div>
    <div class="field" v-if="enhanceForm.inputType === 'Video'">
      <label>反交错</label>
      <select v-model="enhanceForm.deinterlace">
        <option :value="false">关闭</option>
        <option :value="true">启用</option>
      </select>
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
