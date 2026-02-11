<template>
  <div class="panel admin-card">
    <div class="status-row admin-head-row">
      <h2>{{ titleText }}</h2>
      <div class="status-row" style="gap: 8px;">
        <label>全局锁</label>
        <select v-model="localCategory.global_lock" :disabled="loading">
          <option value="free">不约束</option>
          <option value="fixed">全局固定</option>
        </select>
        <button class="secondary" type="button" :disabled="loading" @click="resetLocal">重置</button>
      </div>
    </div>

    <p class="notice" style="margin-bottom: 10px;">
      字段支持三种约束：`不约束`、`固定锁`、`范围锁（数值字段）`。保存后立即影响任务创建面板和后端校验。
    </p>

    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>字段</th>
            <th>类型</th>
            <th>约束模式</th>
            <th>默认值</th>
            <th>固定值</th>
            <th>范围</th>
            <th>可选项</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in fieldRows" :key="row.fieldKey">
            <td>
              <div style="display: grid; gap: 2px;">
                <strong>{{ row.field.label || row.fieldKey }}</strong>
                <span class="notice mono">{{ row.fieldKey }}</span>
              </div>
            </td>
            <td>{{ kindText(row.field.kind) }}</td>
            <td>
              <select :value="row.field.lock" :disabled="loading" @change="onLockChange(row.fieldKey, $event.target.value)">
                <option value="free">不约束</option>
                <option value="fixed">固定锁</option>
                <option v-if="row.field.kind === 'number'" value="range">范围锁</option>
              </select>
            </td>
            <td>
              <template v-if="row.field.kind === 'boolean'">
                <select :value="boolToText(row.field.default_value)" :disabled="loading" @change="updateBool(row.fieldKey, 'default_value', $event.target.value)">
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </template>
              <template v-else-if="row.field.kind === 'number'">
                <input :value="row.field.default_value" type="number" :disabled="loading" @input="updateNumber(row.fieldKey, 'default_value', $event.target.value)" />
              </template>
              <template v-else-if="_usePresetSelector(row.fieldKey, row.field)">
                <select :value="row.field.default_value" :disabled="loading" @change="updateText(row.fieldKey, 'default_value', $event.target.value)">
                  <option v-for="item in _fieldOptionList(row.fieldKey, row.field)" :key="item" :value="item">{{ item }}</option>
                </select>
              </template>
              <template v-else>
                <input :value="row.field.default_value" :disabled="loading" @input="updateText(row.fieldKey, 'default_value', $event.target.value)" />
              </template>
            </td>
            <td>
              <template v-if="row.field.kind === 'boolean'">
                <select :value="boolToText(row.field.fixed_value)" :disabled="loading" @change="updateBool(row.fieldKey, 'fixed_value', $event.target.value)">
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </template>
              <template v-else-if="row.field.kind === 'number'">
                <input :value="row.field.fixed_value" type="number" :disabled="loading" @input="updateNumber(row.fieldKey, 'fixed_value', $event.target.value)" />
              </template>
              <template v-else-if="_usePresetSelector(row.fieldKey, row.field)">
                <select :value="row.field.fixed_value" :disabled="loading" @change="updateText(row.fieldKey, 'fixed_value', $event.target.value)">
                  <option v-for="item in _fieldOptionList(row.fieldKey, row.field)" :key="item" :value="item">{{ item }}</option>
                </select>
              </template>
              <template v-else>
                <input :value="row.field.fixed_value" :disabled="loading" @input="updateText(row.fieldKey, 'fixed_value', $event.target.value)" />
              </template>
            </td>
            <td>
              <template v-if="row.field.kind === 'number'">
                <div class="inline-grid three" style="margin: 0;">
                  <input :value="row.field.min_value" type="number" :disabled="loading" placeholder="min" @input="updateNumber(row.fieldKey, 'min_value', $event.target.value)" />
                  <input :value="row.field.max_value" type="number" :disabled="loading" placeholder="max" @input="updateNumber(row.fieldKey, 'max_value', $event.target.value)" />
                  <input :value="row.field.step" type="number" :disabled="loading" placeholder="step" @input="updateNumber(row.fieldKey, 'step', $event.target.value)" />
                </div>
              </template>
              <template v-else>
                <span class="notice">-</span>
              </template>
            </td>
            <td>
              <template v-if="row.field.kind === 'enum' || row.field.kind === 'string'">
                <AdminModernMultiSelect
                  :model-value="row.field.allowed_values || []"
                  :options="_fieldOptionList(row.fieldKey, row.field)"
                  :disabled="loading"
                  :allow-custom="true"
                  placeholder="搜索并回车添加，可多选"
                  @update:model-value="updateAllowedValues(row.fieldKey, $event)"
                />
              </template>
              <template v-else>
                <span class="notice">-</span>
              </template>
            </td>
          </tr>
          <tr v-if="!fieldRows.length">
            <td colspan="7" class="notice">当前类别无可配置字段</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button type="button" :disabled="loading" @click="save">{{ loading ? "保存中..." : "保存约束" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import AdminModernMultiSelect from "./AdminModernMultiSelect.vue";

const props = defineProps({
  categoryKey: {
    type: String,
    required: true,
  },
  categoryLabel: {
    type: String,
    required: true,
  },
  categoryConfig: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  error: {
    type: String,
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  onSave: {
    type: Function,
    required: true,
  },
  fieldOptionPresets: {
    type: Object,
    default: () => ({}),
  },
});

const localCategory = reactive({
  global_lock: "free",
  fields: {},
});

const cloneCategory = (source) => {
  const raw = source && typeof source === "object" ? source : { global_lock: "free", fields: {} };
  return JSON.parse(JSON.stringify(raw));
};

const setLocalFromProps = () => {
  const cloned = cloneCategory(props.categoryConfig);
  localCategory.global_lock = cloned.global_lock || "free";
  localCategory.fields = cloned.fields || {};
};

watch(
  () => props.categoryConfig,
  () => {
    setLocalFromProps();
  },
  { immediate: true, deep: true }
);

const titleText = computed(() => `${props.categoryLabel}参数约束`);

const fieldRows = computed(() => {
  const entries = Object.entries(localCategory.fields || {});
  return entries.map(([fieldKey, field]) => ({ fieldKey, field: field || {} }));
});

const kindText = (kind) => {
  const map = {
    number: "数值",
    enum: "枚举",
    boolean: "布尔",
    string: "文本",
  };
  return map[kind] || kind || "-";
};

const boolToText = (value) => (value ? "true" : "false");

const _normalizeOptionList = (values) =>
  Array.from(
    new Set(
      (Array.isArray(values) ? values : [])
        .map((item) => String(item ?? "").trim())
        .filter((item) => item.length > 0)
    )
  );

const _fieldPresetBase = (fieldKey) => _normalizeOptionList(props.fieldOptionPresets?.[fieldKey]);

const _fieldOptionList = (fieldKey, field) => {
  const preset = _fieldPresetBase(fieldKey);
  const sticky = _normalizeOptionList([field?.default_value, field?.fixed_value, ...(field?.allowed_values || [])]);
  return _normalizeOptionList([...preset, ...sticky]);
};

const _usePresetSelector = (fieldKey, field) => {
  if (!field || (field.kind !== "enum" && field.kind !== "string")) return false;
  return _fieldPresetBase(fieldKey).length > 0;
};

const updateField = (fieldKey, updater) => {
  if (!localCategory.fields[fieldKey]) return;
  updater(localCategory.fields[fieldKey]);
};

const onLockChange = (fieldKey, lock) => {
  updateField(fieldKey, (field) => {
    if (field.kind !== "number" && lock === "range") {
      field.lock = "free";
      return;
    }
    field.lock = lock;
  });
};

const updateText = (fieldKey, prop, value) => {
  updateField(fieldKey, (field) => {
    field[prop] = value;
  });
};

const updateNumber = (fieldKey, prop, value) => {
  updateField(fieldKey, (field) => {
    if (String(value).trim() === "") {
      field[prop] = null;
      return;
    }
    const parsed = Number(value);
    field[prop] = Number.isFinite(parsed) ? parsed : field[prop];
  });
};

const updateBool = (fieldKey, prop, value) => {
  updateField(fieldKey, (field) => {
    field[prop] = String(value) === "true";
  });
};

const updateAllowedValues = (fieldKey, values) => {
  updateField(fieldKey, (field) => {
    field.allowed_values = (Array.isArray(values) ? values : [])
      .map((item) => String(item || "").trim())
      .filter((item) => item.length > 0);
  });
};

const save = async () => {
  await props.onSave(props.categoryKey, cloneCategory(localCategory));
};

const resetLocal = () => {
  setLocalFromProps();
};
</script>
