<template>
  <div class="panel admin-card">
    <h2>后端管理登录</h2>
    <p class="notice">请输入管理密码以查看任务调度与访问统计。</p>
    <div class="field">
      <label>管理密码</label>
      <input :value="password" type="password" placeholder="输入密码" @input="onInput" @keyup.enter="onLogin" />
    </div>
    <div class="action-row">
      <button :disabled="loading" @click="onLogin">{{ loading ? "登录中..." : "登录" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
  </div>
</template>

<script setup>
defineProps({
  password: {
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
  onLogin: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:password"]);

const onInput = (event) => {
  emit("update:password", event.target.value);
};
</script>
