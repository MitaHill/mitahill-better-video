<template>
  <div>
    <div class="progress" style="margin: 12px 0;"><span :style="{ width: `${status.progress || 0}%` }"></span></div>
    <p class="notice">{{ status.message }}</p>
    <p v-if="progressDetails" class="notice">{{ progressDetails }}</p>

    <div class="panel" style="margin-top: 16px; background: rgba(255,255,255,0.05);">
      <p class="notice">文件：{{ status.video_info?.filename || '未知' }}</p>
      <p class="notice">分辨率：{{ resolution }}</p>
      <p class="notice">大小：{{ status.video_info?.size_mb || 0 }} MB</p>
      <p class="notice" v-if="status.video_info?.video_count">批量视频：{{ status.video_info.video_count }}</p>
      <p class="notice" v-if="status.video_info?.audio_count !== undefined">批量音频：{{ status.video_info.audio_count }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  status: {
    type: Object,
    required: true,
  },
  progressDetails: {
    type: String,
    required: true,
  },
  resolution: {
    type: String,
    required: true,
  },
});
</script>
