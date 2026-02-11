<template>
  <aside class="admin-sidebar" :class="{ 'is-open': open }">
    <div class="admin-sidebar-head">
      <div class="admin-sidebar-title">管理中心</div>
      <button class="secondary admin-sidebar-close" type="button" @click="emit('close')">收起</button>
    </div>

    <div class="field admin-sidebar-search">
      <label>搜索菜单</label>
      <input :value="query" placeholder="模糊匹配，如: 任务 / 模型 / 密码" @input="onSearch" />
    </div>

    <div class="admin-sidebar-list">
      <div v-for="level1 in filteredTree" :key="level1.key" class="admin-nav-group">
        <button class="admin-nav-group-toggle" type="button" @click="toggleNode(level1.key)">
          <span class="admin-nav-group-title">{{ level1.label }}</span>
          <span class="admin-nav-group-chevron" :class="{ 'is-open': isNodeOpen(level1.key) }">▾</span>
        </button>

        <div v-show="isNodeOpen(level1.key)" class="admin-nav-sub-list">
          <div v-for="level2 in level1.children || []" :key="level2.key" class="admin-nav-subgroup">
            <button class="admin-nav-subgroup-toggle" type="button" @click="toggleNode(level2.key)">
              <span class="admin-nav-subgroup-title">{{ level2.label }}</span>
              <span class="admin-nav-group-chevron" :class="{ 'is-open': isNodeOpen(level2.key) }">▾</span>
            </button>

            <div v-show="isNodeOpen(level2.key)" class="admin-nav-third-list">
              <button
                v-for="item in level2.children || []"
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
        </div>
      </div>
      <p v-if="!filteredTree.length" class="notice">没有匹配的菜单项</p>
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
  filteredTree: {
    type: Array,
    required: true,
  },
});

const emit = defineEmits(["update:query", "select", "close"]);
const openNodes = reactive({});

const onSearch = (event) => {
  emit("update:query", event.target.value);
};

const isNodeOpen = (key) => {
  if (Object.prototype.hasOwnProperty.call(openNodes, key)) return Boolean(openNodes[key]);
  return true;
};

const toggleNode = (key) => {
  openNodes[key] = !isNodeOpen(key);
};

const ensureOpenKeys = (nodes) => {
  for (const level1 of nodes || []) {
    if (!Object.prototype.hasOwnProperty.call(openNodes, level1.key)) {
      openNodes[level1.key] = true;
    }
    for (const level2 of level1.children || []) {
      if (!Object.prototype.hasOwnProperty.call(openNodes, level2.key)) {
        openNodes[level2.key] = true;
      }
    }
  }
};

watch(
  () => props.filteredTree,
  (tree) => {
    ensureOpenKeys(tree);
    if (props.query.trim()) {
      for (const level1 of tree || []) {
        openNodes[level1.key] = true;
        for (const level2 of level1.children || []) {
          openNodes[level2.key] = true;
        }
      }
    }
  },
  { immediate: true, deep: true }
);
</script>
