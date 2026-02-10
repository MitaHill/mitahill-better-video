<template>
  <div>
    <div class="field">
      <label>任务 ID</label>
      <input :value="statusQuery" placeholder="粘贴任务 ID" @input="onStatusInput" />
    </div>

    <div class="status-row">
      <button class="secondary" @click="onFetchStatus">查询</button>
      <div v-if="status" :class="['status-pill', statusClass]">{{ status.status }}</div>
      <button v-if="status && status.status === 'COMPLETED'" @click="onDownloadResult">下载</button>
    </div>

    <div v-if="taskIds.length" class="notice task-id-panel" style="margin-top: 12px;">
      <div class="task-id-header"><span>任务 ID：</span></div>
      <div class="task-id-list"><span v-for="id in taskIds" :key="id" class="task-id-item">{{ id }}</span></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  statusQuery: {
    type: String,
    required: true,
  },
  status: {
    type: Object,
    default: null,
  },
  statusClass: {
    type: String,
    required: true,
  },
  taskIds: {
    type: Array,
    required: true,
  },
  onFetchStatus: {
    type: Function,
    required: true,
  },
  onDownloadResult: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:statusQuery"]);

const onStatusInput = (event) => {
  emit("update:statusQuery", event.target.value);
};
</script>
