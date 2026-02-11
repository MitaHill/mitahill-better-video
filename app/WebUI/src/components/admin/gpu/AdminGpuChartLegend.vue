<template>
  <div class="admin-gpu-legend">
    <div v-for="line in lines" :key="`legend-${line.key}`" class="admin-gpu-legend-item">
      <span class="admin-gpu-legend-dot" :style="{ backgroundColor: line.color }"></span>
      <span>{{ line.label }}</span>
      <span class="notice">当前 {{ line.latest }}%，峰值 {{ line.peak }}%</span>
    </div>
    <p v-if="!lines.length && !loading" class="notice">当前时间窗口内暂无 GPU 采样数据。</p>
  </div>
</template>

<script setup>
defineProps({
  lines: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
});
</script>
