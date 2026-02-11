<template>
  <div class="panel admin-card">
    <div class="status-row admin-head-row">
      <h2>GPU 使用率统计</h2>
      <div class="status-row" style="gap: 8px;">
        <select :value="rangeSeconds" :disabled="loading" @change="onSelectRange">
          <option v-for="item in rangeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <button class="secondary" type="button" :disabled="loading" @click="onRefresh">
          {{ loading ? "读取中..." : "刷新" }}
        </button>
      </div>
    </div>

    <AdminGpuChartSvg :lines="chartData.lines" :device-infos="chartData.deviceInfos" />
    <AdminGpuChartLegend :lines="chartData.lines" :loading="loading" />

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed } from "vue";

import AdminGpuChartLegend from "./gpu/AdminGpuChartLegend.vue";
import AdminGpuChartSvg from "./gpu/AdminGpuChartSvg.vue";
import { GPU_RANGE_OPTIONS, buildGpuChartData } from "./gpu/chartMath";

const props = defineProps({
  series: {
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
  rangeSeconds: {
    type: Number,
    required: true,
  },
  onRangeChange: {
    type: Function,
    required: true,
  },
  onRefresh: {
    type: Function,
    required: true,
  },
});

const rangeOptions = GPU_RANGE_OPTIONS;
const chartData = computed(() => buildGpuChartData(props.series));

const onSelectRange = (event) => {
  const value = Number(event.target.value || 60);
  props.onRangeChange(value);
};
</script>
