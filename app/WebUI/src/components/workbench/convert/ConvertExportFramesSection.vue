<template>
  <div class="param-section" v-if="convertForm.convertMode === 'export_frames'">
    <div class="param-title">导出帧参数</div>
    <div class="field compact">
      <label>导出帧率（fps）</label>
      <input v-model.number="convertForm.frameExportFps" type="number" min="0" max="120" placeholder="0=导出全部帧" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
});
</script>
