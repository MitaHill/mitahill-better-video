<template>
  <div class="param-group">
    <div class="param-section">
      <div class="param-title">视频下载来源</div>
      <div class="field">
        <label>视频链接（支持 YouTube 等）</label>
        <input
          :value="downloadForm.sourceUrl"
          type="text"
          placeholder="https://www.youtube.com/watch?v=..."
          @input="onUrlInput"
        />
      </div>

      <div class="status-row" style="gap: 8px;">
        <button type="button" class="secondary" :disabled="downloadForm.probeLoading" @click="onProbeSource">
          {{ downloadForm.probeLoading ? "解析中..." : "解析清晰度与字幕" }}
        </button>
        <span class="notice" v-if="downloadForm.maxQualityLabel">
          免登录可用最高：{{ downloadForm.maxQualityLabel }}
        </span>
      </div>
      <p v-if="downloadForm.probeError" class="notice" style="color: var(--accent-2);">{{ downloadForm.probeError }}</p>
      <p v-if="downloadForm.probeMessage" class="notice">{{ downloadForm.probeMessage }}</p>

      <div class="inline-grid three">
        <div class="field compact">
          <label>下载类型</label>
          <select :value="downloadForm.downloadMode" @change="onModeChange">
            <option value="video">视频</option>
            <option value="audio">仅音频</option>
            <option value="subtitle_only">仅字幕</option>
          </select>
        </div>
      </div>

      <div v-if="downloadForm.downloadMode === 'video'" class="inline-grid three">
        <div class="field compact">
          <label>清晰度（可用格式）</label>
          <select :value="downloadForm.qualitySelector" @change="onQualityChange">
            <option v-for="item in downloadForm.qualityOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </div>
        <div class="field compact">
          <label>输出封装</label>
          <select :value="downloadForm.videoOutputFormat" @change="onVideoFormatChange">
            <option value="mp4">MP4</option>
            <option value="webm">WEBM</option>
            <option value="mkv">MKV</option>
          </select>
        </div>
      </div>

      <div v-if="downloadForm.downloadMode === 'audio'" class="inline-grid three">
        <div class="field compact">
          <label>音频格式</label>
          <select :value="downloadForm.audioOutputFormat" @change="onAudioFormatChange">
            <option value="mp3">MP3</option>
            <option value="m4a">M4A</option>
            <option value="wav">WAV</option>
            <option value="flac">FLAC</option>
          </select>
        </div>
      </div>

      <div v-if="downloadForm.downloadMode === 'subtitle_only'" class="inline-grid two">
        <div class="field compact">
          <label>字幕格式</label>
          <select :value="downloadForm.subtitleOutputFormat" @change="onSubtitleFormatChange">
            <option value="srt">SRT</option>
            <option value="vtt">VTT</option>
          </select>
        </div>
        <div class="field compact">
          <label>包含自动字幕</label>
          <select :value="String(downloadForm.subtitleIncludeAuto)" @change="onIncludeAutoChange">
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </div>
        <div class="field compact" style="grid-column: 1 / -1;">
          <label>字幕语言（多选）</label>
          <select multiple size="6" :value="downloadForm.subtitleLanguages" @change="onSubtitleLanguagesChange">
            <option
              v-for="item in downloadForm.subtitleLanguagesOptions"
              :key="item.code"
              :value="item.code"
            >
              {{ item.label }}{{ item.code === "all" ? "" : item.has_manual ? " | 人工" : "" }}{{ item.code === "all" ? "" : item.has_auto ? " | 自动" : "" }}
            </option>
          </select>
        </div>
      </div>

      <p class="notice">
        下载任务将生成任务ID，可在右侧状态面板查询进度。任务完成后点击“下载”即通过浏览器下载到本地；
        服务器会在下载后自动清理临时文件。
      </p>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  downloadForm: {
    type: Object,
    required: true,
  },
  onProbeSource: {
    type: Function,
    required: true,
  },
});

const onUrlInput = (event) => {
  props.downloadForm.sourceUrl = event.target.value;
};

const onProbeSource = () => {
  if (typeof props.onProbeSource === "function") {
    props.onProbeSource();
  }
};

const onModeChange = (event) => {
  props.downloadForm.downloadMode = String(event.target.value || "video");
};

const onQualityChange = (event) => {
  props.downloadForm.qualitySelector = String(event.target.value || "bestvideo*+bestaudio/best");
};

const onVideoFormatChange = (event) => {
  props.downloadForm.videoOutputFormat = String(event.target.value || "mp4");
};

const onAudioFormatChange = (event) => {
  props.downloadForm.audioOutputFormat = String(event.target.value || "mp3");
};

const onSubtitleFormatChange = (event) => {
  props.downloadForm.subtitleOutputFormat = String(event.target.value || "srt");
};

const onIncludeAutoChange = (event) => {
  props.downloadForm.subtitleIncludeAuto = String(event.target.value || "true").toLowerCase() === "true";
};

const onSubtitleLanguagesChange = (event) => {
  const selected = Array.from(event.target.selectedOptions || []).map((item) => String(item.value || ""));
  props.downloadForm.subtitleLanguages = selected.filter(Boolean);
};
</script>
