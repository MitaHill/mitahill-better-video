<template>
  <div class="preview-grid">
    <div class="preview">
      <p class="notice">原始预览</p>
      <img v-if="preview.original" :key="preview.originalKey" :src="preview.original" />
      <p v-if="!preview.original" class="notice">未生成</p>
    </div>
    <div class="preview">
      <p class="notice">放大预览</p>
      <img v-if="preview.upscaled" :key="preview.upscaledKey" :src="preview.upscaled" />
      <p v-if="!preview.upscaled" class="notice">未生成</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  preview: {
    type: Object,
    required: true,
  },
});
</script>
