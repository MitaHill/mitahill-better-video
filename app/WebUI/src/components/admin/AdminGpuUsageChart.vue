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

    <div class="admin-gpu-chart-wrap">
      <svg class="admin-gpu-chart" viewBox="0 0 1000 280" preserveAspectRatio="none" aria-label="GPU utilization chart">
        <line v-for="y in [0, 25, 50, 75, 100]" :key="`grid-${y}`" :x1="40" :x2="980" :y1="yToSvg(y)" :y2="yToSvg(y)" class="admin-gpu-grid-line" />
        <polyline
          v-for="line in chartLines"
          :key="line.key"
          :points="line.points"
          :stroke="line.color"
          class="admin-gpu-series-line"
        />
      </svg>
      <div class="admin-gpu-y-labels">
        <span v-for="y in [100, 75, 50, 25, 0]" :key="`label-${y}`">{{ y }}%</span>
      </div>
    </div>

    <div class="admin-gpu-legend">
      <div v-for="line in chartLines" :key="`legend-${line.key}`" class="admin-gpu-legend-item">
        <span class="admin-gpu-legend-dot" :style="{ backgroundColor: line.color }"></span>
        <span>{{ line.label }}</span>
        <span class="notice">当前 {{ line.latest }}%，峰值 {{ line.peak }}%</span>
      </div>
      <p v-if="!chartLines.length && !loading" class="notice">当前时间窗口内暂无 GPU 采样数据。</p>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed } from "vue";

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

const rangeOptions = Object.freeze([
  { value: 60, label: "最近 1 分钟" },
  { value: 300, label: "最近 5 分钟" },
  { value: 900, label: "最近 15 分钟" },
  { value: 3600, label: "最近 1 小时" },
]);

const palette = Object.freeze(["#4f8cff", "#3fd0a4", "#f4a261", "#ff6b6b"]);

const toNum = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const yToSvg = (y) => {
  const clamped = Math.max(0, Math.min(100, Number(y)));
  return 20 + ((100 - clamped) / 100) * 240;
};

const chartLines = computed(() => {
  const rows = Array.isArray(props.series) ? props.series : [];
  const maxSamples = rows.reduce((acc, item) => Math.max(acc, (item?.samples || []).length), 0);
  const span = Math.max(1, maxSamples - 1);
  const chartWidth = 940;
  const chartLeft = 40;

  return rows.map((item, index) => {
    const samples = Array.isArray(item?.samples) ? item.samples : [];
    const points = samples
      .map((sample, sampleIndex) => {
        const x = chartLeft + (sampleIndex / span) * chartWidth;
        const y = yToSvg(toNum(sample?.utilization_gpu, 0));
        return `${x},${y}`;
      })
      .join(" ");
    const values = samples.map((sample) => toNum(sample?.utilization_gpu, 0));
    const latest = values.length ? values[values.length - 1].toFixed(1) : "0.0";
    const peak = values.length ? Math.max(...values).toFixed(1) : "0.0";
    return {
      key: `${item?.gpu_index ?? index}`,
      color: palette[index % palette.length],
      points,
      latest,
      peak,
      label: `GPU ${item?.gpu_index ?? index}${item?.gpu_name ? ` (${item.gpu_name})` : ""}`,
    };
  });
});

const onSelectRange = (event) => {
  const value = Number(event.target.value || 60);
  props.onRangeChange(value);
};
</script>
