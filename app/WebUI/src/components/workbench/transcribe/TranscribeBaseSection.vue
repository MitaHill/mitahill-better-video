<template>
  <div class="param-section">
    <div class="param-title">转录基础</div>

    <div class="field">
      <label>上传音频或视频（可多选）</label>
      <input type="file" multiple accept="video/*,audio/*" @change="onTranscribeMediaChange" />
    </div>

    <div class="media-list" v-if="transcribeMediaInfo.length">
      <div class="media-row" v-for="item in transcribeMediaInfo" :key="item.filename + ':' + item.size_mb">
        <span>{{ item.filename }}</span>
        <span>{{ item.has_video ? "视频" : item.has_audio ? "音频" : "未知" }}</span>
        <span v-if="item.duration">{{ Math.round(item.duration) }}s</span>
        <span v-if="item.audio_sample_rate">{{ item.audio_sample_rate }} Hz</span>
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>转录类型</label>
        <select v-model="transcribeForm.transcribeMode">
          <option value="subtitle_zip">字幕与文本（ZIP）</option>
          <option value="subtitled_video">生成带字幕视频</option>
        </select>
      </div>
      <div class="field compact">
        <label>字幕格式</label>
        <select v-model="transcribeForm.subtitleFormat">
          <option value="srt">SRT</option>
          <option value="vtt">VTT</option>
        </select>
      </div>
    </div>

    <div class="inline-grid two">
      <div class="field compact">
        <label>Whisper 模型</label>
        <select v-model="transcribeForm.whisperModel">
          <option value="small">small</option>
          <option value="medium">medium</option>
          <option value="large-v3">large-v3</option>
          <option value="turbo">turbo</option>
        </select>
      </div>
      <div class="field compact">
        <label>语言</label>
        <input v-model="transcribeForm.language" placeholder="auto / zh / en ..." />
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
  transcribeMediaInfo: {
    type: Array,
    required: true,
  },
  onTranscribeMediaChange: {
    type: Function,
    required: true,
  },
});
</script>
