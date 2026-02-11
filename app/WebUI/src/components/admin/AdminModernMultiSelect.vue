<template>
  <div class="modern-multi" :class="{ disabled }">
    <div class="modern-multi-head">
      <div class="modern-multi-chips" v-if="selectedValues.length">
        <span v-for="item in selectedValues" :key="item" class="modern-multi-chip">
          <span class="mono">{{ item }}</span>
          <button type="button" :disabled="disabled" @click="removeValue(item)">×</button>
        </span>
      </div>
      <input
        v-model="query"
        :disabled="disabled"
        :placeholder="placeholderText"
        @keydown.enter.prevent="onEnter"
      />
    </div>

    <div class="modern-multi-toolbar">
      <button type="button" class="secondary mini" :disabled="disabled || !filteredOptions.length" @click="selectFiltered">
        全选筛选结果
      </button>
      <button type="button" class="secondary mini" :disabled="disabled || !selectedValues.length" @click="clearAll">
        清空
      </button>
      <span class="notice">已选 {{ selectedValues.length }} 项</span>
    </div>

    <div class="modern-multi-list">
      <button
        v-for="item in filteredOptions"
        :key="item"
        type="button"
        class="modern-multi-item"
        :class="{ selected: selectedSet.has(item) }"
        :disabled="disabled"
        @click="toggle(item)"
      >
        <span>{{ selectedSet.has(item) ? "✓" : "+" }}</span>
        <span class="mono">{{ item }}</span>
      </button>

      <button
        v-if="canCreateCustom"
        type="button"
        class="modern-multi-item custom"
        :disabled="disabled"
        @click="createCustom"
      >
        <span>+</span>
        <span class="mono">添加 "{{ normalizedQuery }}"</span>
      </button>

      <p v-if="!filteredOptions.length && !canCreateCustom" class="notice">无匹配选项</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  options: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  allowCustom: {
    type: Boolean,
    default: true,
  },
  placeholder: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["update:modelValue"]);

const query = ref("");

const normalizeList = (items) =>
  Array.from(
    new Set(
      (Array.isArray(items) ? items : [])
        .map((item) => String(item ?? "").trim())
        .filter((item) => item.length > 0)
    )
  );

const selectedValues = ref(normalizeList(props.modelValue));

watch(
  () => props.modelValue,
  (value) => {
    selectedValues.value = normalizeList(value);
  },
  { deep: true }
);

const selectedSet = computed(() => new Set(selectedValues.value));

const normalizedQuery = computed(() => String(query.value || "").trim());
const normalizedOptions = computed(() =>
  normalizeList([...(props.options || []), ...selectedValues.value])
);

const filteredOptions = computed(() => {
  const q = normalizedQuery.value.toLowerCase();
  if (!q) return normalizedOptions.value;
  return normalizedOptions.value.filter((item) => item.toLowerCase().includes(q));
});

const canCreateCustom = computed(() => {
  if (!props.allowCustom) return false;
  const q = normalizedQuery.value;
  if (!q) return false;
  return !selectedSet.value.has(q) && !normalizedOptions.value.includes(q);
});

const placeholderText = computed(() => props.placeholder || "搜索并回车添加");

const emitUpdate = (next) => {
  const normalized = normalizeList(next);
  selectedValues.value = normalized;
  emit("update:modelValue", normalized);
};

const toggle = (item) => {
  const safe = String(item || "").trim();
  if (!safe) return;
  if (selectedSet.value.has(safe)) {
    emitUpdate(selectedValues.value.filter((value) => value !== safe));
    return;
  }
  emitUpdate([...selectedValues.value, safe]);
};

const removeValue = (item) => {
  const safe = String(item || "").trim();
  emitUpdate(selectedValues.value.filter((value) => value !== safe));
};

const clearAll = () => {
  emitUpdate([]);
};

const selectFiltered = () => {
  const merged = normalizeList([...selectedValues.value, ...filteredOptions.value]);
  emitUpdate(merged);
};

const createCustom = () => {
  const q = normalizedQuery.value;
  if (!q) return;
  emitUpdate([...selectedValues.value, q]);
  query.value = "";
};

const onEnter = () => {
  if (!normalizedQuery.value) return;
  if (filteredOptions.value.length === 1) {
    toggle(filteredOptions.value[0]);
    query.value = "";
    return;
  }
  if (canCreateCustom.value) {
    createCustom();
  }
};
</script>

<style scoped>
.modern-multi {
  border: 1px solid var(--border);
  background: var(--input-bg);
  padding: 8px;
  display: grid;
  gap: 8px;
}

.modern-multi.disabled {
  opacity: 0.72;
}

.modern-multi-head {
  display: grid;
  gap: 6px;
}

.modern-multi-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.modern-multi-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  background: var(--surface-strong);
  padding: 3px 8px;
}

.modern-multi-chip button {
  min-height: 0;
  padding: 0;
  width: 18px;
  height: 18px;
  line-height: 18px;
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
}

.modern-multi-head input {
  width: 100%;
}

.modern-multi-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.modern-multi-toolbar .mini {
  min-height: 30px;
  padding: 5px 10px;
  font-size: 0.78rem;
}

.modern-multi-list {
  max-height: 172px;
  overflow: auto;
  border: 1px solid var(--border);
  background: var(--surface);
  padding: 6px;
  display: grid;
  gap: 5px;
}

.modern-multi-item {
  min-height: 28px;
  text-align: left;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  width: 100%;
}

.modern-multi-item.selected {
  background: color-mix(in srgb, var(--accent) 22%, var(--surface));
  border-color: color-mix(in srgb, var(--accent) 52%, var(--border));
}

.modern-multi-item.custom {
  border-style: dashed;
}
</style>
