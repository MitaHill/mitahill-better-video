<template>
  <div class="panel workbench-panel workbench-panel--status">
    <h2>查询状态</h2>

    <StatusQueryHeader
      :status-query="statusQuery"
      :status="status"
      :status-class="statusClass"
      :progress-value="status?.progress || 0"
      :task-ids="taskIds"
      :on-fetch-status="fetchStatus"
      :on-download-result="downloadResult"
      @update:status-query="onStatusQueryChange"
    />

    <div v-if="status" style="margin-top: 16px;">
      <StatusProgressSummary
        :status="status"
        :live="live"
        :progress-details="progressDetails"
        :resolution="resolution"
      />

      <StatusPreviewGrid v-if="isPreviewSupported && status.status !== 'PENDING'" :preview="preview" />

      <div v-if="status.is_batch && status.children?.length" class="notice" style="margin-top: 14px;">
        <div v-for="item in status.children" :key="item.task_id" style="display: flex; justify-content: space-between; gap: 12px; padding: 4px 0;">
          <span>{{ item.task_id }} · {{ item.item_label || item.task_category }}</span>
          <span>{{ item.status }} · {{ Math.round(item.progress || 0) }}%</span>
        </div>
      </div>

      <StatusParamTable v-if="status.task_params" :param-rows="paramRows" />
    </div>

    <p v-if="statusError" class="notice" style="color: var(--accent-2); margin-top: 12px;">{{ statusError }}</p>
  </div>
</template>

<script setup>
import StatusParamTable from "./status/StatusParamTable.vue";
import StatusPreviewGrid from "./status/StatusPreviewGrid.vue";
import StatusProgressSummary from "./status/StatusProgressSummary.vue";
import StatusQueryHeader from "./status/StatusQueryHeader.vue";

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
  progressDetails: {
    type: String,
    required: true,
  },
  resolution: {
    type: String,
    required: true,
  },
  taskIds: {
    type: Array,
    required: true,
  },
  preview: {
    type: Object,
    required: true,
  },
  live: {
    type: Object,
    required: true,
  },
  isPreviewSupported: {
    type: Boolean,
    required: true,
  },
  paramRows: {
    type: Array,
    required: true,
  },
  statusError: {
    type: String,
    required: true,
  },
  fetchStatus: {
    type: Function,
    required: true,
  },
  downloadResult: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:statusQuery"]);

const onStatusQueryChange = (value) => {
  emit("update:statusQuery", value);
};
</script>
