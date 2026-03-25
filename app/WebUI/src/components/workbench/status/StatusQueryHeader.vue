<template>
  <div>
    <div class="field">
      <label>任务 ID</label>
      <div class="task-pin-field">
        <input
          v-for="(digit, index) in pinDigits"
          :key="index"
          :ref="(el) => setPinInputRef(el, index)"
          :value="digit"
          :class="['task-pin-box', 'task-pin-input', { 'is-active': activeIndex === index, 'is-filled': Boolean(digit) }]"
          inputmode="numeric"
          pattern="[0-9]*"
          maxlength="1"
          autocomplete="one-time-code"
          @focus="onPinFocus(index)"
          @blur="onPinBlur"
          @input="onPinInput(index, $event)"
          @keydown="onPinKeydown(index, $event)"
          @paste="onPinPaste(index, $event)"
        />
      </div>
      <p class="notice" style="margin-top: 10px;">输入 4 位数字任务 ID</p>
    </div>

    <div class="status-row">
      <button class="secondary" @click="onFetchStatus">查询</button>
      <div v-if="status" :class="['status-pill', statusClass]">{{ statusText(status.status) }}</div>
      <button v-if="status && status.status === 'COMPLETED'" @click="onDownloadResult">下载</button>
    </div>

    <div v-if="taskIds.length" class="notice task-id-panel" style="margin-top: 12px;">
      <div class="task-id-header"><span>任务 ID：</span></div>
      <div class="task-id-list">
        <button
          v-for="id in taskIds"
          :key="id"
          type="button"
          class="task-id-item"
          @click="selectTaskId(id)"
        >
          {{ id }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";

const PIN_LENGTH = 4;

const props = defineProps({
  statusQuery: {
    type: String,
    required: true,
  },
  status: {
    type: Object,
    default: null,
  },
  statusClass: {
    type: String,
    required: true,
  },
  taskIds: {
    type: Array,
    required: true,
  },
  onFetchStatus: {
    type: Function,
    required: true,
  },
  onDownloadResult: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:statusQuery"]);
const pinInputRefs = ref([]);
const isFocused = ref(false);
const focusedIndex = ref(-1);

const pinDigits = computed(() => Array.from({ length: PIN_LENGTH }, (_, index) => props.statusQuery[index] || ""));
const activeIndex = computed(() => {
  if (!isFocused.value) return -1;
  if (focusedIndex.value >= 0) return focusedIndex.value;
  return Math.min(props.statusQuery.length, PIN_LENGTH - 1);
});

const normalizeDigits = (value) => String(value || "").replace(/\D+/g, "").slice(0, PIN_LENGTH);

const setPinInputRef = (el, index) => {
  if (el) {
    pinInputRefs.value[index] = el;
  }
};

const focusPin = (index) => {
  pinInputRefs.value[index]?.focus();
  pinInputRefs.value[index]?.select?.();
};

const emitDigits = (digits) => {
  emit("update:statusQuery", digits.join(""));
};

const scheduleAutoFetch = (digits) => {
  if (!digits.every(Boolean)) return;
  nextTick(() => {
    props.onFetchStatus();
  });
};

const fillDigitsFrom = (startIndex, rawValue) => {
  const chars = normalizeDigits(rawValue).split("");
  const digits = [...pinDigits.value];
  let nextIndex = startIndex;
  for (const char of chars) {
    if (nextIndex >= PIN_LENGTH) break;
    digits[nextIndex] = char;
    nextIndex += 1;
  }
  emitDigits(digits);
  const focusIndex = Math.min(nextIndex, PIN_LENGTH - 1);
  nextTick(() => {
    if (chars.length) {
      focusPin(focusIndex);
    }
  });
  scheduleAutoFetch(digits);
};

const onPinFocus = (index) => {
  isFocused.value = true;
  focusedIndex.value = index;
  pinInputRefs.value[index]?.select?.();
};

const onPinBlur = () => {
  isFocused.value = false;
  focusedIndex.value = -1;
};

const onPinInput = (index, event) => {
  const rawValue = String(event.target.value || "");
  if (!rawValue) {
    const digits = [...pinDigits.value];
    digits[index] = "";
    emitDigits(digits);
    return;
  }
  fillDigitsFrom(index, rawValue);
};

const onPinKeydown = (index, event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    props.onFetchStatus();
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    focusPin(Math.max(0, index - 1));
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    focusPin(Math.min(PIN_LENGTH - 1, index + 1));
    return;
  }
  if (event.key === "Backspace" && !pinDigits.value[index] && index > 0) {
    event.preventDefault();
    const digits = [...pinDigits.value];
    digits[index - 1] = "";
    emitDigits(digits);
    nextTick(() => {
      focusPin(index - 1);
    });
  }
};

const onPinPaste = (index, event) => {
  event.preventDefault();
  fillDigitsFrom(index, event.clipboardData?.getData("text") || "");
};

const selectTaskId = (taskId) => {
  emit("update:statusQuery", taskId);
  nextTick(() => {
    focusPin(PIN_LENGTH - 1);
    props.onFetchStatus();
  });
};

const statusText = (status) => {
  const map = {
    PENDING: "排队中",
    PROCESSING: "处理中",
    COMPLETED: "已完成",
    FAILED: "失败",
  };
  return map[status] || status || "-";
};
</script>
