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
import { computeActiveIndex, computeSliderStyle, resolveTabs } from "./topTabsLayout";

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

const safeTabs = computed(() => resolveTabs(props.tabs));

const activeIndex = computed(() => computeActiveIndex(safeTabs.value, props.activeCategory));

const tabVars = computed(() => ({
  "--tab-count": String(Math.max(1, safeTabs.value.length)),
}));

const sliderStyle = computed(() => computeSliderStyle(activeIndex.value, safeTabs.value.length));
</script>
