<template>
  <div class="admin-gpu-chart-wrap">
    <svg class="admin-gpu-chart" viewBox="0 0 1000 280" preserveAspectRatio="none" aria-label="GPU utilization chart">
      <line
        v-for="y in [0, 25, 50, 75, 100]"
        :key="`grid-${y}`"
        :x1="40"
        :x2="980"
        :y1="yToSvg(y)"
        :y2="yToSvg(y)"
        class="admin-gpu-grid-line"
      />
      <polyline
        v-for="line in lines"
        :key="line.key"
        :points="line.points"
        :stroke="line.color"
        class="admin-gpu-series-line"
      />
    </svg>
    <div class="admin-gpu-y-labels">
      <span v-for="y in [100, 75, 50, 25, 0]" :key="`label-${y}`">{{ y }}%</span>
    </div>
    <div class="admin-gpu-device-info" v-if="deviceText">
      {{ deviceText }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

import { yToSvg } from "./chartMath";

const props = defineProps({
  lines: {
    type: Array,
    required: true,
  },
  deviceInfos: {
    type: Array,
    required: true,
  },
});

const deviceText = computed(() =>
  (Array.isArray(props.deviceInfos) ? props.deviceInfos : [])
    .map((item) => String(item?.label || "").trim())
    .filter((item) => item.length > 0)
    .join(" | ")
);
</script>
