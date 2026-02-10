<template>
  <aside class="admin-sidebar" :class="{ 'is-open': open }">
    <div class="admin-sidebar-head">
      <div class="admin-sidebar-title">后端管理</div>
      <button class="secondary admin-sidebar-close" type="button" @click="emit('close')">收起</button>
    </div>

    <div class="field admin-sidebar-search">
      <label>搜索菜单</label>
      <input :value="query" placeholder="模糊匹配，如: 任务 / 代理 / 密码" @input="onSearch" />
    </div>

    <div class="admin-sidebar-list">
      <div v-for="group in filteredGroups" :key="group.key" class="admin-nav-group">
        <button class="admin-nav-group-toggle" type="button" @click="toggleGroup(group.key)">
          <span class="admin-nav-group-title">{{ group.label }}</span>
          <span class="admin-nav-group-chevron" :class="{ 'is-open': isGroupOpen(group.key) }">▾</span>
        </button>
        <div v-show="isGroupOpen(group.key)" class="admin-nav-sub-list">
          <button
            v-for="item in group.children"
            :key="item.key"
            class="admin-nav-item"
            :class="{ 'is-active': item.key === activeKey }"
            type="button"
            @click="emit('select', item.key)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
      <p v-if="!filteredGroups.length" class="notice">没有匹配的菜单项</p>
    </div>
  </aside>
</template>

<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  query: {
    type: String,
    required: true,
  },
  activeKey: {
    type: String,
    required: true,
  },
  filteredGroups: {
    type: Array,
    required: true,
  },
});

const emit = defineEmits(["update:query", "select", "close"]);
const openGroups = reactive({});

const onSearch = (event) => {
  emit("update:query", event.target.value);
};

const isGroupOpen = (key) => {
  if (Object.prototype.hasOwnProperty.call(openGroups, key)) return Boolean(openGroups[key]);
  return true;
};

const toggleGroup = (key) => {
  openGroups[key] = !isGroupOpen(key);
};

watch(
  () => props.filteredGroups,
  (groups) => {
    for (const group of groups || []) {
      if (!Object.prototype.hasOwnProperty.call(openGroups, group.key)) {
        openGroups[group.key] = true;
      }
      if (props.query.trim()) {
        openGroups[group.key] = true;
      }
    }
  },
  { immediate: true, deep: true }
);
</script>
