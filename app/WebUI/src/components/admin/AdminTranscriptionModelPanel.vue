<template>
  <div class="panel admin-card">
    <div class="status-row admin-head-row">
      <h2>转录模型目录与下载</h2>
      <div class="status-row" style="gap: 8px;">
        <button class="secondary" type="button" :disabled="loading" @click="onRefresh">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </div>

    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>模型</th>
            <th>后端</th>
            <th>引擎</th>
            <th>已安装</th>
            <th>存储路径</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in models" :key="`${item.backend}:${item.model_id}`">
            <td class="mono">{{ item.model_id }}</td>
            <td>{{ item.backend }}</td>
            <td>{{ item.engine }}</td>
            <td>{{ item.installed ? "是" : "否" }}</td>
            <td class="mono">{{ item.local_path }}</td>
            <td>
              <button
                type="button"
                :disabled="loading"
                @click="onDownload(item.backend, item.model_id)"
              >
                下载
              </button>
            </td>
          </tr>
          <tr v-if="!models.length">
            <td colspan="6" class="notice">暂无模型数据</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div style="margin-top: 14px;">
      <h3 style="margin-bottom: 8px;">下载任务</h3>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>任务ID</th>
              <th>模型</th>
              <th>后端</th>
              <th>状态</th>
              <th>进度</th>
              <th>消息</th>
              <th>更新时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.job_id">
              <td class="mono">{{ job.job_id }}</td>
              <td class="mono">{{ job.model_id }}</td>
              <td>{{ job.backend }}</td>
              <td>{{ job.status }}</td>
              <td style="min-width: 180px;">
                <div class="progress" style="height: 8px; margin-bottom: 4px;">
                  <span :style="{ width: `${Number(job.progress || 0)}%` }"></span>
                </div>
                <span class="notice">{{ Number(job.progress || 0).toFixed(1) }}%</span>
              </td>
              <td>{{ job.message || job.error || "-" }}</td>
              <td>{{ formatDateTimeToSecond(job.updated_at) }}</td>
            </tr>
            <tr v-if="!jobs.length">
              <td colspan="7" class="notice">暂无下载任务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
import { formatDateTimeToSecond } from "./formatDateTime";

defineProps({
  models: {
    type: Array,
    required: true,
  },
  jobs: {
    type: Array,
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
  message: {
    type: String,
    required: true,
  },
  onRefresh: {
    type: Function,
    required: true,
  },
  onDownload: {
    type: Function,
    required: true,
  },
});
</script>
