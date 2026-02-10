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
            <th>任务ID</th>
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
          <tr v-for="task in tasks" :key="task.task_id">
            <td class="mono">{{ task.task_id }}</td>
            <td>{{ task.task_category || "-" }}</td>
            <td>{{ statusText(task.status) }}</td>
            <td>{{ task.progress ?? 0 }}%</td>
            <td class="mono">{{ task.client_ip || "unknown" }}</td>
            <td>{{ task.created_at || "-" }}</td>
            <td>{{ task.updated_at || "-" }}</td>
            <td>{{ task.message || "-" }}</td>
          </tr>
          <tr v-if="!tasks.length">
            <td colspan="8" class="notice">暂无任务记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
  </div>
</template>

<script setup>
defineProps({
  tasks: {
    type: Array,
    required: true,
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
});

const emit = defineEmits(["update:statusFilter"]);

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
</script>
