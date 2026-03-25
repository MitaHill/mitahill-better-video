<template>
  <div class="status-progress-shell">
    <div class="status-progress-head">
      <div>
        <div class="status-progress-percent">{{ progressValue }}%</div>
        <p class="notice">{{ status.message }}</p>
        <p v-if="progressDetails" class="notice">{{ progressDetails }}</p>
      </div>
    </div>

    <div class="progress" style="margin: 12px 0;"><span :style="{ width: `${progressValue}%` }"></span></div>
    <div v-if="subProgressPercent !== null" class="progress status-progress-sub">
      <span :style="{ width: `${subProgressPercent}%` }"></span>
    </div>

    <div class="status-live-grid">
      <div class="status-live-card">
        <div class="status-live-label">当前阶段</div>
        <strong>{{ stageLabel || "-" }}</strong>
      </div>
      <div class="status-live-card">
        <div class="status-live-label">当前项</div>
        <strong>{{ itemText }}</strong>
      </div>
      <div class="status-live-card">
        <div class="status-live-label">子进度</div>
        <strong>{{ unitText }}</strong>
      </div>
      <div class="status-live-card">
        <div class="status-live-label">GPU</div>
        <strong>{{ gpuText }}</strong>
      </div>
      <div class="status-live-card">
        <div class="status-live-label">最近更新</div>
        <strong>{{ updateText }}</strong>
      </div>
    </div>

    <div class="panel" style="margin-top: 16px; background: rgba(255,255,255,0.05);">
      <p class="notice">文件：{{ status.video_info?.filename || "未知" }}</p>
      <p v-if="showResolutionRow" class="notice">分辨率：{{ resolution }}</p>
      <p v-if="showSizeRow" class="notice">大小：{{ sizeText }}</p>
      <p class="notice" v-if="status.video_info?.video_count">批量视频：{{ status.video_info.video_count }}</p>
      <p class="notice" v-if="status.video_info?.audio_count !== undefined">批量音频：{{ status.video_info.audio_count }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { resolveStageLabel } from "../../../composables/workbench/statusViewBuilders";

const props = defineProps({
  status: {
    type: Object,
    required: true,
  },
  live: {
    type: Object,
    required: true,
  },
  liveNowMs: {
    type: Number,
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
});

const clampPercent = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, Math.round(numeric)));
};

const progressValue = computed(() => clampPercent(props.status.progress || 0));
const category = computed(() => String(props.status?.task_params?.task_category || "").trim().toLowerCase());
const stageLabel = computed(() => resolveStageLabel(props.live.stage, category.value));

const itemText = computed(() => {
  const label = String(props.live.itemLabel || "").trim();
  const index = Number(props.live.itemIndex || 0);
  const count = Number(props.live.itemCount || 0);
  if (!count) return "-";
  return `${label || "当前项"} ${index}/${count}`;
});

const unitText = computed(() => {
  const label = String(props.live.unitLabel || "").trim();
  const done = Number(props.live.unitDone || 0);
  const total = Number(props.live.unitTotal || 0);
  if (!total) return "-";
  return `${label || "进度"} ${done}/${total}`;
});

const gpuText = computed(() => {
  if (props.live.gpu === null || props.live.gpu === undefined || props.live.gpu === "") {
    return "-";
  }
  const value = Number(props.live.gpu);
  return Number.isFinite(value) ? `${Math.round(value)}%` : "-";
});

const subProgressPercent = computed(() => {
  const total = Number(props.live.unitTotal || 0);
  if (!total) return null;
  const done = Number(props.live.unitDone || 0);
  return clampPercent((done / total) * 100);
});

const updateText = computed(() => {
  const updated = Number(props.live.updatedAtMs || 0);
  if (!updated) return "等待事件";
  const diffSec = Math.max(0, Math.floor((props.liveNowMs - updated) / 1000));
  if (diffSec <= 1) return "刚刚更新";
  if (diffSec < 60) return `${diffSec}s前`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m前`;
  return `${Math.floor(diffMin / 60)}h前`;
});

const sizeText = computed(() => {
  const value = Number(props.status?.video_info?.size_mb || 0);
  return value > 0 ? `${value} MB` : "-";
});

const showResolutionRow = computed(() => {
  if (category.value !== "download") return true;
  return props.resolution && props.resolution !== "-" && props.resolution !== "?";
});

const showSizeRow = computed(() => {
  if (category.value !== "download") return true;
  return Number(props.status?.video_info?.size_mb || 0) > 0;
});
</script>
