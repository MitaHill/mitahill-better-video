<template>
  <div class="panel admin-card">
    <div class="status-row admin-head-row">
      <h2>系统日志（WARN+）</h2>
      <div class="status-row" style="gap: 8px;">
        <select :value="minLevel" @change="onMinLevelChange">
          <option value="WARNING">WARNING+</option>
          <option value="ERROR">ERROR+</option>
          <option value="CRITICAL">CRITICAL</option>
          <option value="INFO">INFO+</option>
        </select>
        <input :value="loggerName" placeholder="Logger 名称过滤" @input="onLoggerNameInput" />
        <input :value="keyword" placeholder="关键字过滤" @input="onKeywordInput" />
        <button class="secondary" type="button" :disabled="loading" @click="onRefresh">{{ loading ? "刷新中..." : "刷新" }}</button>
      </div>
    </div>

    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>等级</th>
            <th>Logger</th>
            <th>消息</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in logs" :key="row.id">
            <td>{{ formatDateTimeToSecond(row.created_at) }}</td>
            <td>{{ row.level }}</td>
            <td class="mono">{{ row.logger_name }}</td>
            <td>{{ row.message }}</td>
          </tr>
          <tr v-if="!logs.length">
            <td colspan="4" class="notice">暂无日志记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
  </div>
</template>

<script setup>
import { formatDateTimeToSecond } from "./formatDateTime";

const props = defineProps({
  logs: {
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
  minLevel: {
    type: String,
    required: true,
  },
  keyword: {
    type: String,
    required: true,
  },
  loggerName: {
    type: String,
    required: true,
  },
  onRefresh: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:minLevel", "update:keyword", "update:loggerName"]);

const onMinLevelChange = (event) => emit("update:minLevel", event.target.value);
const onKeywordInput = (event) => emit("update:keyword", event.target.value);
const onLoggerNameInput = (event) => emit("update:loggerName", event.target.value);
</script>
