<template>
  <details ref="detailsRef" class="stream-panel" @toggle="onToggle">
    <summary>
      原始信息流（实时）
      <span class="notice" style="margin-left: 8px;">{{ lines.length }} 条</span>
    </summary>
    <p class="notice stream-note">
      展示转录句子与翻译模型原始输出（包含 think 标签与原始文本流，不做清洗）。
    </p>
    <div
      ref="viewportRef"
      :class="['stream-viewport', { 'stream-viewport-near-scrollbar': showScrollbar }]"
      @mousemove="onViewportMouseMove"
      @mouseleave="onViewportMouseLeave"
    >
      <p v-if="!lines.length" class="notice">暂无信息流。</p>
      <div
        v-for="(line, idx) in lines"
        :key="String(line.id || `${line.line_key || '-'}:${idx}`)"
        :class="['stream-line', `stream-${String(line.channel || 'general').replace(/[^a-z0-9_-]/gi, '')}`]"
      >
        <span class="stream-prefix">{{ prefixFor(line) }}</span>
        <span class="stream-text">{{ line.text }}</span>
      </div>
    </div>
  </details>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
  lines: {
    type: Array,
    required: true,
  },
});

const detailsRef = ref(null);
const viewportRef = ref(null);
const showScrollbar = ref(false);
const SCROLLBAR_REVEAL_EDGE_PX = 22;

const prefixFor = (line) => {
  const channel = String(line?.channel || "general").trim().toLowerCase();
  const segmentIndex = Number(line?.segment_index || 0);
  if (channel === "asr") {
    return segmentIndex > 0 ? `转录 ${segmentIndex}` : "转录";
  }
  if (channel === "translation_raw") {
    return segmentIndex > 0 ? `翻译源 ${segmentIndex}` : "翻译源";
  }
  if (channel === "translation_progress") {
    return "翻译进度";
  }
  return "信息";
};

const scrollToBottom = (smooth = true) => {
  const target = viewportRef.value;
  if (!target) return;
  target.scrollTo({
    top: target.scrollHeight,
    behavior: smooth ? "smooth" : "auto",
  });
};

const onToggle = () => {
  if (detailsRef.value?.open) {
    nextTick(() => scrollToBottom(false));
  }
};

const onViewportMouseMove = (event) => {
  const target = viewportRef.value;
  if (!target) {
    showScrollbar.value = false;
    return;
  }
  const rect = target.getBoundingClientRect();
  showScrollbar.value = rect.right - event.clientX <= SCROLLBAR_REVEAL_EDGE_PX;
};

const onViewportMouseLeave = () => {
  showScrollbar.value = false;
};

watch(
  () => props.lines,
  async () => {
    if (!detailsRef.value?.open) return;
    await nextTick();
    scrollToBottom(false);
  },
  { deep: true }
);
</script>
