<template>
  <div class="panel admin-card">
    <h2>翻译源设置</h2>
    <p class="notice" style="margin-bottom: 10px;">用于配置转录后的翻译链路，调试菜单可直接测试当前配置。</p>

    <div class="inline-grid two">
      <div class="field compact">
        <label>翻译提供器</label>
        <select v-model="local.provider" :disabled="loading">
          <option value="none">不启用</option>
          <option value="ollama">Ollama</option>
          <option value="openai_compatible">OpenAI Compatible</option>
        </select>
      </div>
      <div class="field compact">
        <label>超时(s)</label>
        <input v-model.number="local.timeoutSec" :disabled="loading" type="number" min="1" max="1200" />
      </div>
    </div>

    <div class="field compact">
      <label>极端情况回退策略</label>
      <select v-model="local.fallbackMode" :disabled="loading">
        <option value="model_full_text">模型返回全文</option>
        <option value="source_text">原始待翻译文本</option>
      </select>
      <p class="notice" style="margin-top: 6px;">
        当无法提取代码块时生效：可回退到“模型返回全文”或“原始待翻译文本”。
      </p>
    </div>

    <div class="field compact">
      <label>服务地址</label>
      <input v-model="local.baseUrl" :disabled="loading" placeholder="例如: http://127.0.0.1:11434 或 https://api.openai.com/v1" />
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>模型名</label>
        <input v-model="local.model" :disabled="loading" placeholder="例如: qwen2.5:7b / gpt-4o-mini" />
      </div>
      <div class="field compact">
        <label>API Key</label>
        <input v-model="local.apiKey" :disabled="loading" placeholder="可为空" />
      </div>
    </div>

    <div class="field compact">
      <label>系统提示词</label>
      <textarea v-model="local.prompt" :disabled="loading" rows="4" placeholder="翻译系统提示词"></textarea>
      <p class="notice" style="margin-top: 6px;">
        支持变量：<code v-pre>{{target_language}}</code>、<code v-pre>{{target_language_name}}</code>、<code v-pre>{{target_language_code}}</code>。
        程序会自动追加严格翻译规则（只输出译文、保留格式与占位符）。
      </p>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button :disabled="loading" type="button" @click="save">{{ loading ? "保存中..." : "保存翻译设置" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
  </div>
</template>

<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
  configData: {
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
});

const local = reactive({
  provider: "none",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSec: 120,
  prompt: "",
  fallbackMode: "model_full_text",
});

const applyFromProps = () => {
  const cfg = props.configData || {};
  const translation = cfg.translation || {};
  local.provider = translation.provider || "none";
  local.baseUrl = translation.base_url || "";
  local.model = translation.model || "";
  local.apiKey = translation.api_key || "";
  local.timeoutSec = Number(translation.timeout_sec ?? 120);
  local.prompt = translation.prompt || "";
  local.fallbackMode = translation.fallback_mode || "model_full_text";
};

watch(
  () => props.configData,
  () => {
    applyFromProps();
  },
  { immediate: true, deep: true }
);

const save = async () => {
  await props.onSave({
    translation: {
      provider: String(local.provider || "none").trim().toLowerCase(),
      base_url: String(local.baseUrl || "").trim(),
      model: String(local.model || "").trim(),
      api_key: String(local.apiKey || "").trim(),
      timeout_sec: Number(local.timeoutSec || 120),
      prompt: String(local.prompt || "").trim(),
      fallback_mode: String(local.fallbackMode || "model_full_text").trim().toLowerCase(),
    },
  });
};
</script>
