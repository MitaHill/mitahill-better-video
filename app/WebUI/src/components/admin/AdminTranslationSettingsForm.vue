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

    <div class="inline-grid three" style="margin-top: 8px;">
      <div class="field compact">
        <label>上下文裁剪窗（轮次）</label>
        <input v-model.number="local.contextWindowSize" :disabled="loading" type="number" min="1" max="50" />
      </div>
      <div class="field compact">
        <label>单次发送滑动窗（句）</label>
        <input v-model.number="local.batchWindowSize" :disabled="loading" type="number" min="1" max="50" />
      </div>
      <div class="field compact">
        <label>单批最大字符数</label>
        <input v-model.number="local.batchMaxChars" :disabled="loading" type="number" min="500" max="20000" />
      </div>
    </div>
    <p class="notice" style="margin-top: 6px;">
      小模型建议调小上下文裁剪窗与单次发送滑动窗（例如 2~4 / 4~8），可降低幻觉与解析失败风险。
      上下文超窗时固定保留第一轮对话，从第二轮开始裁剪。
    </p>

    <div class="field compact">
      <label>极端情况回退策略</label>
      <select v-model="local.fallbackMode" :disabled="loading">
        <option value="source_text">原始待翻译文本</option>
        <option value="model_full_text">模型返回全文（可能混入解释）</option>
      </select>
      <p class="notice" style="margin-top: 6px;">
        当结构化解析失败时生效。推荐“原始待翻译文本”，可避免把模型解释文本写入字幕。
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
        该内容是“自定义前缀提示词”，支持变量：
        <code v-pre>{{target_language}}</code>（示例: Chinese (zh)）、
        <code v-pre>{{target_language_name}}</code>（示例: Chinese）、
        <code v-pre>{{target_language_code}}</code>（示例: zh）。
      </p>
      <p class="notice" style="margin-top: 6px;">
        程序执行顺序：变量替换 -> 自动追加系统严格规则 -> 发送给翻译模型。
        系统严格规则会要求：仅输出结构化结果、禁止解释文本、保留行结构与占位符/标记。
      </p>
      <p class="notice" style="margin-top: 6px;">
        返回解析仅接受 JSON 结构化结果（可在代码块内或纯文本 JSON）。
        一旦出现缺段、重复段、额外段或非结构化内容，则判定失败并自动缩窗重试。
      </p>

      <div class="status-row" style="gap: 8px; margin-top: 8px; flex-wrap: wrap;">
        <button class="secondary" type="button" :disabled="loading" @click="applyPromptTemplate('general')">套用模板：通用稳健</button>
        <button class="secondary" type="button" :disabled="loading" @click="applyPromptTemplate('subtitle')">套用模板：字幕保形</button>
        <button class="secondary" type="button" :disabled="loading" @click="applyPromptTemplate('technical')">套用模板：术语优先</button>
      </div>

      <details style="margin-top: 10px;">
        <summary class="notice" style="cursor: pointer;">查看模板提示词（可直接复制）</summary>
        <div class="notice mono" style="margin-top: 8px; white-space: pre-wrap;">
【模板A：通用稳健】
Translate to {{target_language}}.
Keep original line breaks and segment boundaries.
Preserve placeholders and markup exactly: {name}, [MASK], &lt;tag&gt;, %s, ${VAR}.
Do not add explanations or notes.

【模板B：字幕保形】
Translate subtitles into {{target_language_name}} ({{target_language_code}}).
Keep each line aligned to the source line order.
Do not merge/split lines unless necessary for grammar.
Keep timestamps, numbers, URLs, emails, IDs unchanged.

【模板C：术语优先】
Translate to {{target_language}} with technical accuracy.
Prefer standard technical terminology in {{target_language_name}}.
Keep product names, APIs, code identifiers, and file paths unchanged.
If a term should remain untranslated, keep it as is.
        </div>
      </details>

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
        <label>最终系统提示词预览（变量替换 + 严格规则）</label>
        <textarea :value="previewSystemPrompt" rows="11" readonly />
      </div>
    </div>

    <div class="action-row" style="margin-top: 12px;">
      <button :disabled="loading" type="button" @click="save">{{ loading ? "保存中..." : "保存翻译设置" }}</button>
    </div>
    <p v-if="error" class="notice" style="color: var(--accent-2); margin-top: 10px;">{{ error }}</p>
    <p v-if="message" class="notice" style="margin-top: 8px;">{{ message }}</p>
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
  provider: "none",
  baseUrl: "",
  model: "",
  apiKey: "",
  timeoutSec: 120,
  contextWindowSize: 6,
  batchWindowSize: 10,
  batchMaxChars: 2500,
  prompt: "",
  fallbackMode: "source_text",
  previewTargetLanguage: "zh",
});

const PROMPT_TEMPLATES = Object.freeze({
  general: [
    "Translate to {{target_language}}.",
    "Keep original line breaks and segment boundaries.",
    "Preserve placeholders and markup exactly: {name}, [MASK], <tag>, %s, ${VAR}.",
    "Do not add explanations or notes.",
  ].join("\n"),
  subtitle: [
    "Translate subtitles into {{target_language_name}} ({{target_language_code}}).",
    "Keep each line aligned to the source line order.",
    "Do not merge/split lines unless necessary for grammar.",
    "Keep timestamps, numbers, URLs, emails, IDs unchanged.",
  ].join("\n"),
  technical: [
    "Translate to {{target_language}} with technical accuracy.",
    "Prefer standard technical terminology in {{target_language_name}}.",
    "Keep product names, APIs, code identifiers, and file paths unchanged.",
    "If a term should remain untranslated, keep it as is.",
  ].join("\n"),
});

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
  if (!source) return "";
  const meta = resolveTargetLanguageMeta(targetLanguage);
  return source
    .replaceAll("{{target_language_code}}", meta.code)
    .replaceAll("{{target_language_name}}", meta.name)
    .replaceAll("{{target_language}}", meta.display);
};

const buildStrictRules = (targetLanguage) => {
  const meta = resolveTargetLanguageMeta(targetLanguage);
  const targetLine = meta.code ? `Target language: ${meta.display}` : `Target language: ${meta.name}`;
  return [
    "You are a professional translation engine for transcription segments.",
    targetLine,
    "Return translated text only, with no explanations.",
    "Preserve original line breaks and text structure.",
    "Keep numbers, punctuation, URLs, emails, and IDs unchanged unless translation is required.",
    "Do not translate placeholders or markup, such as {name}, [MASK], <tag>, %s, ${VAR}.",
    "If the source text is empty, return an empty string.",
  ].join("\n");
};

const previewSystemPrompt = computed(() => {
  const custom = renderCustomPrompt(local.prompt, local.previewTargetLanguage);
  const strict = buildStrictRules(local.previewTargetLanguage);
  if (custom) return `${custom}\n\n${strict}`;
  return strict;
});

const applyFromProps = () => {
  const cfg = props.configData || {};
  const translation = cfg.translation || {};
  local.provider = translation.provider || "none";
  local.baseUrl = translation.base_url || "";
  local.model = translation.model || "";
  local.apiKey = translation.api_key || "";
  local.timeoutSec = Number(translation.timeout_sec ?? 120);
  local.contextWindowSize = Number(translation.context_window_size ?? 6);
  local.batchWindowSize = Number(translation.batch_window_size ?? 10);
  local.batchMaxChars = Number(translation.batch_max_chars ?? 2500);
  local.prompt = translation.prompt || "";
  local.fallbackMode = translation.fallback_mode || "source_text";
};

watch(
  () => props.configData,
  () => {
    applyFromProps();
  },
  { immediate: true, deep: true }
);

const applyPromptTemplate = (key) => {
  const template = PROMPT_TEMPLATES[String(key || "").trim().toLowerCase()];
  if (!template) return;
  local.prompt = template;
};

const save = async () => {
  await props.onSave({
    translation: {
      provider: String(local.provider || "none").trim().toLowerCase(),
      base_url: String(local.baseUrl || "").trim(),
      model: String(local.model || "").trim(),
      api_key: String(local.apiKey || "").trim(),
      timeout_sec: Number(local.timeoutSec || 120),
      context_window_size: Number(local.contextWindowSize || 6),
      batch_window_size: Number(local.batchWindowSize || 10),
      batch_max_chars: Number(local.batchMaxChars || 2500),
      prompt: String(local.prompt || "").trim(),
      fallback_mode: String(local.fallbackMode || "source_text").trim().toLowerCase(),
    },
  });
};
</script>
