<template>
  <div class="top-tabs" :style="tabVars" role="tablist" aria-label="功能分类">
    <div class="top-tabs__slider" :style="sliderStyle" aria-hidden="true"></div>
    <button
      v-for="tab in safeTabs"
      :key="tab.key"
      class="top-tabs__btn"
      :class="{ 'is-active': tab.key === activeCategory }"
      type="button"
      role="tab"
      :aria-selected="tab.key === activeCategory"
      @click="emit('switch', tab.key)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  activeCategory: {
    type: String,
    required: true,
  },
  tabs: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["switch"]);

const safeTabs = computed(() => {
  if (Array.isArray(props.tabs) && props.tabs.length) return props.tabs;
  return [
    { key: "enhance", label: "增强" },
    { key: "convert", label: "转换" },
    { key: "transcribe", label: "转录" },
    { key: "download", label: "下载" },
    { key: "admin", label: "管理" },
  ];
});

const activeIndex = computed(() => {
  const idx = safeTabs.value.findIndex((tab) => tab.key === props.activeCategory);
  return idx >= 0 ? idx : 0;
});

const tabVars = computed(() => ({
  "--tab-count": String(Math.max(1, safeTabs.value.length)),
}));

const sliderStyle = computed(() => ({
  width: `calc((100% / ${Math.max(1, safeTabs.value.length)}) * 0.75)`,
  left: `calc(${activeIndex.value} * (100% / ${Math.max(1, safeTabs.value.length)}) + ((100% / ${Math.max(1, safeTabs.value.length)}) * 0.125))`,
}));
</script>
