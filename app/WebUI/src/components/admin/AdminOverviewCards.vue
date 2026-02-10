<template>
  <div class="admin-kpi-grid">
    <div class="admin-kpi-card">
      <div class="admin-kpi-label">总任务</div>
      <div class="admin-kpi-value">{{ counts.total || 0 }}</div>
    </div>
    <div class="admin-kpi-card">
      <div class="admin-kpi-label">排队中</div>
      <div class="admin-kpi-value">{{ counts.pending || 0 }}</div>
    </div>
    <div class="admin-kpi-card">
      <div class="admin-kpi-label">处理中</div>
      <div class="admin-kpi-value">{{ counts.processing || 0 }}</div>
    </div>
    <div class="admin-kpi-card">
      <div class="admin-kpi-label">已完成</div>
      <div class="admin-kpi-value">{{ counts.completed || 0 }}</div>
    </div>
    <div class="admin-kpi-card">
      <div class="admin-kpi-label">失败</div>
      <div class="admin-kpi-value">{{ counts.failed || 0 }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  counts: {
    type: Object,
    required: true,
  },
});
</script>
