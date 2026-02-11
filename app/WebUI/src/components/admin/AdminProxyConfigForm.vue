<template>
  <div class="panel admin-card">
    <h2>受信代理IP配置</h2>
    <p class="notice" style="margin-bottom: 10px;">用于识别真实访客地址，支持 IPv4/IPv6 CIDR，逗号分隔。</p>

    <div class="field">
      <label>受信代理列表</label>
      <textarea :value="trustedProxies" rows="4" @input="onInput"></textarea>
    </div>

    <p class="notice">当前请求识别IP：{{ resolvedClientIp || "-" }}</p>
    <p class="notice" v-if="fromEnvDefault">环境默认：{{ fromEnvDefault }}</p>

    <div class="action-row" style="margin-top: 10px;">
      <button :disabled="loading" @click="onSave">{{ loading ? "保存中..." : "保存代理配置" }}</button>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
defineProps({
  trustedProxies: {
    type: String,
    required: true,
  },
  resolvedClientIp: {
    type: String,
    required: true,
  },
  fromEnvDefault: {
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
  onSave: {
    type: Function,
    required: true,
  },
});

const emit = defineEmits(["update:trustedProxies"]);

const onInput = (event) => {
  emit("update:trustedProxies", event.target.value);
};
</script>
