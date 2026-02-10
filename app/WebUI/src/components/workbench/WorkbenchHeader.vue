<template>
  <div class="app-header">
    <div class="header-left">
      <div class="theme-mini">
        <label for="theme-mode">界面</label>
        <select id="theme-mode" :value="themeMode" @change="onThemeChange">
          <option value="auto">自动</option>
          <option value="dark">深色</option>
          <option value="light">浅色</option>
        </select>
      </div>
      <h1 class="app-title">better_video</h1>
    </div>
    <TopCategoryTabs :active-category="activeCategory" :tabs="CATEGORY_TABS" @switch="onSwitchCategory" />
  </div>
</template>

<script setup>
import TopCategoryTabs from "../navigation/TopCategoryTabs.vue";
import { CATEGORY_TABS } from "../../constants/workbench";

defineProps({
  themeMode: {
    type: String,
    required: true,
  },
  activeCategory: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["update:themeMode", "switchCategory"]);

const onThemeChange = (event) => {
  emit("update:themeMode", event.target.value);
};

const onSwitchCategory = (category) => {
  emit("switchCategory", category);
};
</script>
