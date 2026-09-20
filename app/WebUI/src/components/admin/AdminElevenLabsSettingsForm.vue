<template>
  <div class="panel admin-card">
    <h2>ElevenLabs Scribe</h2>
    <p class="notice" style="margin-bottom: 10px;">用于实验性云端转录，当前固定使用 Scribe v2。</p>

    <div class="field compact">
      <label>API Key</label>
      <input
        v-model="apiKey"
        type="password"
        autocomplete="new-password"
        :disabled="loading"
        :placeholder="configured ? '已配置，留空则保持不变' : '输入 ElevenLabs API Key'"
      />
      <p class="notice" style="margin-top: 6px;">状态：{{ configured ? "已配置" : "未配置" }}</p>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button type="button" :disabled="loading || !apiKey.trim()" @click="save">
        {{ loading ? "保存中..." : "保存" }}
      </button>
      <button class="secondary" type="button" :disabled="loading || testLoading || !configured" @click="onTest">
        {{ testLoading ? "测试中..." : "测试连接" }}
      </button>
      <button class="secondary" type="button" :disabled="loading || !configured" @click="clearKey">移除密钥</button>
    </div>

    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
    <p v-if="testError" class="notice" style="color: var(--accent-2); margin-top: 8px;">{{ testError }}</p>
    <p v-if="testResult" class="notice" style="margin-top: 8px;">
      {{ testResult.message || "连接正常" }} · 套餐 {{ testResult.tier || "unknown" }} · 状态 {{ testResult.status || "unknown" }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  configData: { type: Object, required: true },
  loading: { type: Boolean, required: true },
  error: { type: String, required: true },
  message: { type: String, required: true },
  testLoading: { type: Boolean, required: true },
  testError: { type: String, required: true },
  testResult: { type: Object, default: null },
  onSave: { type: Function, required: true },
  onTest: { type: Function, required: true },
});

const apiKey = ref("");
const configured = computed(() => Boolean(props.configData?.elevenlabs?.api_key_configured));

watch(
  () => props.configData,
  () => {
    apiKey.value = "";
  }
);

const save = async () => {
  const value = apiKey.value.trim();
  if (!value) return;
  await props.onSave({ elevenlabs: { api_key: value } });
};

const clearKey = async () => {
  if (!window.confirm("确认移除 ElevenLabs API Key？")) return;
  await props.onSave({ elevenlabs: { clear_api_key: true } });
};
</script>
