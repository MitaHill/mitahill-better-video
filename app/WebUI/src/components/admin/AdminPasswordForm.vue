<template>
  <div class="panel admin-card">
    <h2>修改管理密码</h2>
    <div class="inline-grid two">
      <div class="field compact">
        <label>旧密码</label>
        <input :value="oldPassword" type="password" @input="onOld" />
      </div>
      <div class="field compact">
        <label>新密码（至少8位）</label>
        <input :value="newPassword" type="password" @input="onNew" />
      </div>
    </div>
    <div class="action-row">
      <button :disabled="loading" @click="onChangePassword">{{ loading ? "提交中..." : "更新密码" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
defineProps({
  oldPassword: {
    type: String,
    required: true,
  },
  newPassword: {
    type: String,
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
  onChangePassword: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:oldPassword", "update:newPassword"]);

const onOld = (event) => {
  emit("update:oldPassword", event.target.value);
};

const onNew = (event) => {
  emit("update:newPassword", event.target.value);
};
</script>
