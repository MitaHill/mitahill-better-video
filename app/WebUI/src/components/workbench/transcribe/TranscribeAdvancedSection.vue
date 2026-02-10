<template>
  <div class="param-section">
    <div class="param-title">转录参数</div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>温度</label>
        <input
          v-model.number="transcribeForm.temperature"
          type="number"
          :step="numStep('temperature', 0.1)"
          :min="numMin('temperature', 0)"
          :max="numMax('temperature', 1)"
          :disabled="isDisabled('temperature')"
        />
      </div>
      <div class="field compact">
        <label>Beam Size</label>
        <input
          v-model.number="transcribeForm.beamSize"
          type="number"
          :min="numMin('beamSize', 1)"
          :max="numMax('beamSize', 20)"
          :step="numStep('beamSize', 1)"
          :disabled="isDisabled('beamSize')"
        />
      </div>
      <div class="field compact">
        <label>Best Of</label>
        <input
          v-model.number="transcribeForm.bestOf"
          type="number"
          :min="numMin('bestOf', 1)"
          :max="numMax('bestOf', 20)"
          :step="numStep('bestOf', 1)"
          :disabled="isDisabled('bestOf')"
        />
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>最大行宽</label>
        <input
          v-model.number="transcribeForm.maxLineChars"
          type="number"
          :min="numMin('maxLineChars', 0)"
          :max="numMax('maxLineChars', 200)"
          :step="numStep('maxLineChars', 1)"
          :disabled="isDisabled('maxLineChars')"
        />
      </div>
      <div class="field compact">
        <label>输出音频码率 (k)</label>
        <input
          v-model.number="transcribeForm.outputAudioBitrateK"
          type="number"
          :min="numMin('outputAudioBitrateK', 32)"
          :max="numMax('outputAudioBitrateK', 1024)"
          :step="numStep('outputAudioBitrateK', 1)"
          :disabled="isDisabled('outputAudioBitrateK')"
        />
      </div>
    </div>

    <div class="inline-grid two">
      <label class="check-inline">
        <input v-model="transcribeForm.prependTimestamps" type="checkbox" :disabled="isDisabled('prependTimestamps')" />
        文本附带时间戳
      </label>
      <div class="field compact" v-if="transcribeForm.transcribeMode === 'subtitled_video'">
        <label>视频编码</label>
        <select v-model="transcribeForm.outputVideoCodec" :disabled="isDisabled('outputVideoCodec')">
          <option v-for="item in outputVideoCodecOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
    </div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>翻译提供器</label>
        <select v-model="transcribeForm.translatorProvider" :disabled="isDisabled('translatorProvider')">
          <option v-for="item in translatorProviderOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>翻译超时(秒)</label>
        <input
          v-model.number="transcribeForm.translatorTimeoutSec"
          type="number"
          :min="numMin('translatorTimeoutSec', 1)"
          :max="numMax('translatorTimeoutSec', 1200)"
          :step="numStep('translatorTimeoutSec', 1)"
          :disabled="isDisabled('translatorTimeoutSec')"
        />
      </div>
      <label class="check-inline">
        <input v-model="transcribeForm.generateBilingual" type="checkbox" :disabled="isDisabled('generateBilingual')" />
        生成双语字幕
      </label>
    </div>

    <label class="check-inline">
      <input v-model="transcribeForm.exportJson" type="checkbox" :disabled="isDisabled('exportJson')" />
      导出 JSON 分段
    </label>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="inline-grid two">
      <div class="field compact">
        <label>翻译服务地址</label>
        <input
          v-model="transcribeForm.translatorBaseUrl"
          placeholder="http://127.0.0.1:11434 或 https://api.xxx/v1"
          :disabled="isDisabled('translatorBaseUrl')"
        />
      </div>
      <div class="field compact">
        <label>翻译模型名</label>
        <input
          v-model="transcribeForm.translatorModel"
          placeholder="qwen3:8b / gpt-4o-mini"
          :disabled="isDisabled('translatorModel')"
        />
      </div>
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译 API Key（可选，OpenAI兼容常用）</label>
      <input
        v-model="transcribeForm.translatorApiKey"
        type="password"
        placeholder="留空则不带 Authorization 头"
        :disabled="isDisabled('translatorApiKey')"
      />
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译提示词（可选）</label>
      <textarea
        v-model="transcribeForm.translatorPrompt"
        rows="4"
        placeholder="留空使用后端默认提示词"
        :disabled="isDisabled('translatorPrompt')"
      ></textarea>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  transcribeForm: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const readPolicy = (fieldKey) => props.getFieldPolicy("transcribe", fieldKey) || null;
const isDisabled = (fieldKey) => Boolean(readPolicy(fieldKey)?.disabled);
const allowed = (fieldKey, fallback = []) => {
  const values = readPolicy(fieldKey)?.allowedValues;
  return Array.isArray(values) && values.length ? values : fallback;
};

const toFiniteOr = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const numMin = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.minValue, fallback);
const numMax = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.maxValue, fallback);
const numStep = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.step, fallback);

const outputVideoCodecOptions = computed(() =>
  allowed("outputVideoCodec", ["h264", "h265"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);

const translatorProviderOptions = computed(() =>
  allowed("translatorProvider", ["none", "ollama", "openai_compatible"]).map((value) => ({
    value,
    label: value === "none" ? "不启用" : value === "ollama" ? "Ollama" : value === "openai_compatible" ? "OpenAI兼容" : value,
  }))
);
</script>
