<template>
  <div class="panel admin-card">
    <div class="status-row admin-head-row">
      <h2>任务状态总览</h2>
      <div class="inline-grid two admin-filters">
        <select :value="statusFilter" @change="onFilterChange">
          <option value="">全部状态</option>
          <option value="PENDING">排队中</option>
          <option value="PROCESSING">处理中</option>
          <option value="COMPLETED">已完成</option>
          <option value="FAILED">失败</option>
        </select>
        <button class="secondary" :disabled="loading" @click="onRefresh">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </div>

    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>操作</th>
            <th>批次/任务ID</th>
            <th>类别</th>
            <th>状态</th>
            <th>进度</th>
            <th>客户端IP</th>
            <th>创建时间</th>
            <th>更新时间</th>
            <th>消息</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tableRows" :key="task.row_key" :class="rowClass(task)">
            <td>
              <button
                v-if="task.is_batch && canDelete(task.status)"
                type="button"
                :disabled="loading || taskActionLoading(task.batch_id)"
                @click="confirmDeleteBatch(task.batch_id)"
              >
                {{ taskActionLoading(task.batch_id) ? "删除中..." : "删除批次" }}
              </button>
              <button
                v-else-if="!task.is_batch && canCancel(task.status)"
                type="button"
                :disabled="loading || taskActionLoading(task.task_id)"
                @click="onCancelTask(task.task_id)"
              >
                {{ taskActionLoading(task.task_id) ? "取消中..." : "取消" }}
              </button>
              <button
                v-else-if="!task.batch_id && canDelete(task.status)"
                type="button"
                :disabled="loading || taskActionLoading(task.task_id)"
                @click="confirmDelete(task.task_id)"
              >
                {{ taskActionLoading(task.task_id) ? "删除中..." : "删除" }}
              </button>
              <span v-else>-</span>
            </td>
            <td class="mono">
              <span class="admin-task-id-cell">
                <button
                  v-if="task.is_batch"
                  type="button"
                  class="secondary admin-batch-toggle"
                  @click="toggleBatch(task.batch_id)"
                >
                  {{ isBatchExpanded(task.batch_id) ? "▾" : "▸" }}
                </button>
                <span v-if="task.is_child" class="admin-child-branch"></span>
                <span class="admin-task-id-main">{{ task.task_id }}</span>
                <span v-if="task.is_batch" class="admin-row-badge">批次</span>
                <span v-else-if="task.is_child" class="admin-row-badge admin-row-badge--child">属于 {{ task.batch_id }}</span>
                <span v-else class="admin-row-badge admin-row-badge--single">单任务</span>
              </span>
            </td>
            <td>{{ task.task_category || "-" }}</td>
            <td>{{ statusText(task.status) }}</td>
            <td>{{ task.progress ?? 0 }}%</td>
            <td class="mono">{{ task.client_ip || "unknown" }}</td>
            <td>{{ formatDateTimeToSecond(task.created_at) }}</td>
            <td>{{ formatDateTimeToSecond(task.updated_at) }}</td>
            <td>{{ task.message || "-" }}</td>
          </tr>
          <tr v-if="!tableRows.length">
            <td colspan="9" class="notice">暂无任务记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed, reactive } from "vue";
import { formatDateTimeToSecond } from "./formatDateTime";

const props = defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  batches: {
    type: Array,
    default: () => [],
  },
  statusFilter: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  error: {
    type: String,
    required: true,
  },
  onRefresh: {
    type: Function,
    required: true,
  },
  onCancelTask: {
    type: Function,
    required: true,
  },
  onDeleteTask: {
    type: Function,
    required: true,
  },
  onDeleteBatch: {
    type: Function,
    required: true,
  },
  taskActionLoading: {
    type: Function,
    default: () => false,
  },
});

const emit = defineEmits(["update:statusFilter"]);
const expandedBatches = reactive({});

const taskMap = computed(() => {
  const map = {};
  for (const task of props.tasks) {
    map[task.task_id] = task;
  }
  return map;
});

const tableRows = computed(() => {
  const rows = [];
  const batchedTaskIds = new Set();

  for (const batch of props.batches) {
    rows.push({
      ...batch,
      row_key: `batch-${batch.batch_id}`,
      is_batch: true,
      task_id: batch.batch_id,
    });
    for (const child of batch.children || []) {
      batchedTaskIds.add(child.task_id);
    }
    if (!expandedBatches[batch.batch_id]) continue;
    for (const child of batch.children || []) {
      const fullTask = taskMap.value[child.task_id] || {};
      rows.push({
        ...child,
        ...fullTask,
        row_key: `batch-${batch.batch_id}-task-${child.task_id}`,
        is_child: true,
        batch_id: batch.batch_id,
        task_id: child.task_id,
        task_category: fullTask.task_category || child.task_category || batch.task_category,
        status: fullTask.status || child.status,
        progress: fullTask.progress ?? child.progress ?? 0,
        message: fullTask.message || child.message || child.item_label || "-",
      });
    }
  }

  for (const task of props.tasks) {
    if (task.batch_id || batchedTaskIds.has(task.task_id)) continue;
    rows.push({ ...task, row_key: `task-${task.task_id}` });
  }
  return rows;
});

const rowClass = (task) => ({
  "admin-task-row--batch": task.is_batch,
  "admin-task-row--child": task.is_child,
  "admin-task-row--single": !task.is_batch && !task.is_child,
});

const onFilterChange = (event) => {
  emit("update:statusFilter", event.target.value);
};

const statusText = (status) => {
  const map = {
    PENDING: "排队中",
    PROCESSING: "处理中",
    COMPLETED: "已完成",
    FAILED: "失败",
  };
  return map[status] || status || "-";
};

const canCancel = (status) => {
  const raw = String(status || "").toUpperCase();
  return raw === "PENDING" || raw === "PROCESSING";
};

const canDelete = (status) => {
  const raw = String(status || "").toUpperCase();
  return raw === "COMPLETED" || raw === "FAILED";
};

const isBatchExpanded = (batchId) => Boolean(expandedBatches[batchId]);

const toggleBatch = (batchId) => {
  expandedBatches[batchId] = !expandedBatches[batchId];
};

const confirmDelete = (taskId) => {
  if (!window.confirm(`确认删除任务 ${taskId}？相关文件和数据库记录将被永久删除。`)) return;
  props.onDeleteTask(taskId);
};

const confirmDeleteBatch = (batchId) => {
  if (!window.confirm(`确认删除批次 ${batchId}？该批次下所有任务文件和数据库记录将被永久删除。`)) return;
  props.onDeleteBatch(batchId);
};
</script>
