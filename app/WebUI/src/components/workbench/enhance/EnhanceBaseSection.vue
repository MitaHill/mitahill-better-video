<template>
  <div class="param-section">
    <div class="param-title">任务基础</div>
    <div class="field">
      <label>输入类型</label>
      <select v-model="enhanceForm.inputType">
        <option value="Video">视频</option>
        <option value="Image">图片</option>
      </select>
    </div>
    <div class="field">
      <label>上传文件（支持批量）</label>
      <input type="file" multiple @change="onEnhanceFileChange" />
    </div>
  </div>
</template>

<script setup>
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
