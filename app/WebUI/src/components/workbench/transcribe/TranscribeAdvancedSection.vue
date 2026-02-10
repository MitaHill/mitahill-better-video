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
