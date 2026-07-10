<template>
  <div class="panel admin-card">
    <h2>翻译源设置</h2>
    <p class="notice" style="margin-bottom: 10px;">用于配置转录后的翻译链路，调试菜单可直接测试当前配置。</p>

    <div class="inline-grid two">
      <div class="field compact">
        <label>翻译提供器</label>
        <input :value="'OpenAI 兼容格式'" disabled />
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
      <input v-model="local.baseUrl" :disabled="loading" placeholder="例如: http://127.0.0.1:8000/v1 或 https://api.example.com/v1" />
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>模型名</label>
        <input v-model="local.model" :disabled="loading" placeholder="例如: qwen2.5:7b / gpt-4o-mini" />
      </div>
      <div class="field compact">
        <label>API Key</label>
        <input v-model="local.apiKey" :disabled="loading" placeholder="按兼容服务要求填写，可留空" />
      </div>
    </div>

    <div class="field compact">
      <label>系统提示词</label>
      <textarea v-model="local.prompt" :disabled="loading" rows="4" placeholder="翻译系统提示词"></textarea>
      <p class="notice" style="margin-top: 6px;">
        该内容是“自定义前缀提示词”，支持变量：
        <code v-pre>{{target_language}}</code>（示例: Chinese (zh)）、
        <code v-pre>{{target_language_name}}</code>（示例: Chinese）、
        <code v-pre>{{target_language_code}}</code>（示例: zh）。
      </p>
      <p class="notice" style="margin-top: 6px;">
        程序执行顺序：变量替换 -> 自动追加英文核心提示词 -> 携带最近 20 轮上下文发送给翻译模型。
      </p>
      <p class="notice" style="margin-top: 6px;">
        返回解析顺序：若模型输出包含代码块 <code>```Translation```</code>，优先提取代码块正文；
        若没有代码块，则按“极端情况回退策略”决定使用“模型返回全文”或“原始待翻译文本”。
      </p>

      <div class="inline-grid two" style="margin-top: 12px;">
        <div class="field compact">
          <label>预览目标语言</label>
          <select v-model="local.previewTargetLanguage" :disabled="loading">
            <option
              v-for="item in previewLanguageOptions"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </option>
          </select>
        </div>
      </div>
      <div class="field compact">
        <label>最终系统提示词预览（变量替换 + 核心提示词）</label>
        <textarea :value="previewSystemPrompt" rows="11" readonly />
      </div>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button :disabled="loading" type="button" @click="save">{{ loading ? "保存中..." : "保存翻译设置" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
    <p class="notice" style="margin-top: 10px;">
      如果本地部署模型，建议使用 vLLM 或 Ollama 提供 OpenAI 兼容格式。
    </p>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from "vue";
import { TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS } from "../../constants/transcriptionLanguages";

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
  provider: "openai_compatible",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSec: 120,
  prompt: "",
  fallbackMode: "model_full_text",
  previewTargetLanguage: "zh",
});

const CORE_TRANSLATION_PROMPT = "Place the translation in a code block; do not add explanations. For example: ```Translation```";
const LEGACY_CORE_TRANSLATION_PROMPTS = new Set([
  CORE_TRANSLATION_PROMPT,
  "将译文放到代码块中，不要增加解释。例如```译文```",
]);

const TARGET_LANGUAGE_NAME_MAP = Object.freeze({
  zh: "Chinese",
  en: "English",
  ja: "Japanese",
  ko: "Korean",
  es: "Spanish",
  fr: "French",
  de: "German",
  ru: "Russian",
  ar: "Arabic",
  pt: "Portuguese",
  it: "Italian",
  nl: "Dutch",
  pl: "Polish",
  tr: "Turkish",
  uk: "Ukrainian",
  cs: "Czech",
  sv: "Swedish",
  no: "Norwegian",
  da: "Danish",
  fi: "Finnish",
  el: "Greek",
  he: "Hebrew",
  hi: "Hindi",
  id: "Indonesian",
  ms: "Malay",
  vi: "Vietnamese",
  th: "Thai",
});

const previewLanguageOptions = computed(() => TRANSCRIPTION_TARGET_LANGUAGE_OPTIONS);

const resolveTargetLanguageMeta = (targetLanguage) => {
  const code = String(targetLanguage || "").trim().toLowerCase();
  const name = TARGET_LANGUAGE_NAME_MAP[code] || code || "target-language";
  const display = code ? `${name} (${code})` : name;
  return { code, name, display };
};

const renderCustomPrompt = (rawPrompt, targetLanguage) => {
  const source = String(rawPrompt || "").trim();
  if (!source || LEGACY_CORE_TRANSLATION_PROMPTS.has(source)) return "";
  const meta = resolveTargetLanguageMeta(targetLanguage);
  return source
    .replaceAll("{{target_language_code}}", meta.code)
    .replaceAll("{{target_language_name}}", meta.name)
    .replaceAll("{{target_language}}", meta.display);
};

const buildStrictRules = () => CORE_TRANSLATION_PROMPT;

const previewSystemPrompt = computed(() => {
  const custom = renderCustomPrompt(local.prompt, local.previewTargetLanguage);
  const strict = buildStrictRules(local.previewTargetLanguage);
  if (custom) return `${custom}\n\n${strict}`;
  return strict;
});

const applyFromProps = () => {
  const cfg = props.configData || {};
  const translation = cfg.translation || {};
  local.provider = "openai_compatible";
  local.baseUrl = translation.base_url || "";
  local.model = translation.model || "";
  local.apiKey = translation.api_key || "";
  local.timeoutSec = Number(translation.timeout_sec ?? 120);
  const prompt = String(translation.prompt || "").trim();
  local.prompt = LEGACY_CORE_TRANSLATION_PROMPTS.has(prompt) ? "" : prompt;
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
      provider: "openai_compatible",
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
