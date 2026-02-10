<template>
  <div class="param-section">
    <div class="param-title">转录参数</div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>温度</label>
        <input v-model.number="transcribeForm.temperature" type="number" step="0.1" min="0" max="1" />
      </div>
      <div class="field compact">
        <label>Beam Size</label>
        <input v-model.number="transcribeForm.beamSize" type="number" min="1" max="20" />
      </div>
      <div class="field compact">
        <label>Best Of</label>
        <input v-model.number="transcribeForm.bestOf" type="number" min="1" max="20" />
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>最大行宽</label>
        <input v-model.number="transcribeForm.maxLineChars" type="number" min="0" max="200" />
      </div>
      <div class="field compact">
        <label>输出音频码率 (k)</label>
        <input v-model.number="transcribeForm.outputAudioBitrateK" type="number" min="32" max="1024" />
      </div>
    </div>

    <div class="inline-grid two">
      <label class="check-inline">
        <input v-model="transcribeForm.prependTimestamps" type="checkbox" />
        文本附带时间戳
      </label>
      <div class="field compact" v-if="transcribeForm.transcribeMode === 'subtitled_video'">
        <label>视频编码</label>
        <select v-model="transcribeForm.outputVideoCodec">
          <option value="h264">H264</option>
          <option value="h265">H265</option>
        </select>
      </div>
    </div>

    <div class="inline-grid three">
      <div class="field compact">
        <label>翻译提供器</label>
        <select v-model="transcribeForm.translatorProvider">
          <option value="none">不启用</option>
          <option value="ollama">Ollama</option>
          <option value="openai_compatible">OpenAI兼容</option>
        </select>
      </div>
      <div class="field compact">
        <label>翻译超时(秒)</label>
        <input v-model.number="transcribeForm.translatorTimeoutSec" type="number" min="1" max="1200" />
      </div>
      <label class="check-inline">
        <input v-model="transcribeForm.generateBilingual" type="checkbox" />
        生成双语字幕
      </label>
    </div>

    <label class="check-inline">
      <input v-model="transcribeForm.exportJson" type="checkbox" />
      导出 JSON 分段
    </label>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="inline-grid two">
      <div class="field compact">
        <label>翻译服务地址</label>
        <input v-model="transcribeForm.translatorBaseUrl" placeholder="http://127.0.0.1:11434 或 https://api.xxx/v1" />
      </div>
      <div class="field compact">
        <label>翻译模型名</label>
        <input v-model="transcribeForm.translatorModel" placeholder="qwen3:8b / gpt-4o-mini" />
      </div>
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译 API Key（可选，OpenAI兼容常用）</label>
      <input v-model="transcribeForm.translatorApiKey" type="password" placeholder="留空则不带 Authorization 头" />
    </div>

    <div v-if="transcribeForm.translateTo && transcribeForm.translatorProvider !== 'none'" class="field compact">
      <label>翻译提示词（可选）</label>
      <textarea
        v-model="transcribeForm.translatorPrompt"
        rows="4"
        placeholder="留空使用后端默认提示词"
      ></textarea>
    </div>
  </div>
</template>

<script setup>
defineProps({
  transcribeForm: {
    type: Object,
    required: true,
  },
});
</script>
