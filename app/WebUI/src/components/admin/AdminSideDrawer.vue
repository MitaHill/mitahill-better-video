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
      <button
        v-for="item in filteredItems"
        :key="item.key"
        class="admin-nav-item"
        :class="{ 'is-active': item.key === activeKey }"
        type="button"
        @click="emit('select', item.key)"
      >
        {{ item.label }}
      </button>
      <p v-if="!filteredItems.length" class="notice">没有匹配的菜单项</p>
    </div>
  </aside>
</template>

<script setup>
defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  query: {
    type: String,
    required: true,
  },
  items: {
    type: Array,
    required: true,
  },
  activeKey: {
    type: String,
    required: true,
  },
  filteredItems: {
    type: Array,
    required: true,
  },
});

const emit = defineEmits(["update:query", "select", "close"]);

const onSearch = (event) => {
  emit("update:query", event.target.value);
};
</script>
