<template>
  <div class="panel">
    <h2>查询状态</h2>

    <StatusQueryHeader
      :status-query="statusQuery"
      :status="status"
      :status-class="statusClass"
      :task-ids="taskIds"
      :on-fetch-status="fetchStatus"
      :on-download-result="downloadResult"
      @update:status-query="onStatusQueryChange"
    />

    <div v-if="status" style="margin-top: 16px;">
      <StatusProgressSummary
        :status="status"
        :progress-details="progressDetails"
        :resolution="resolution"
        :translation-progress-text="translationProgressText"
      />
      <StatusRawStreamPanel
        v-if="String(status?.task_params?.task_category || '').trim().toLowerCase() === 'transcribe'"
        :lines="streamLines"
      />

      <StatusPreviewGrid v-if="isPreviewSupported && status.status !== 'PENDING'" :preview="preview" />

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
import StatusRawStreamPanel from "./status/StatusRawStreamPanel.vue";

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
  streamLines: {
    type: Array,
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
  translationProgressText: {
    type: String,
    default: "",
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
