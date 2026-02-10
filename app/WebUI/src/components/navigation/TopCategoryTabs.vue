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
    { key: "enhance", label: "视频增强" },
    { key: "convert", label: "视频转换" },
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
  transform: `translateX(calc(${activeIndex.value} * 100%))`,
}));
</script>
