<template>
  <div class="param-group">
    <div class="param-section">
      <div class="param-title">视频下载来源</div>
      <div class="field">
        <label>视频链接（支持 YouTube 等）</label>
        <input
          :value="downloadForm.url"
          type="text"
          placeholder="https://www.youtube.com/watch?v=..."
          @input="onUrlInput"
        />
      </div>

      <div class="inline-grid three">
        <div class="field compact">
          <label>输出格式</label>
          <select :value="downloadForm.outputFormat" @change="onFormatChange">
            <option value="mp4">MP4</option>
            <option value="webm">WEBM</option>
            <option value="mkv">MKV</option>
            <option value="mp3">MP3（音频）</option>
            <option value="m4a">M4A（音频）</option>
          </select>
        </div>
        <div class="field compact">
          <label>仅音频</label>
          <select :value="String(downloadForm.audioOnly)" @change="onAudioOnlyChange">
            <option value="false">否</option>
            <option value="true">是</option>
          </select>
        </div>
      </div>

      <p class="notice">
        当前为直连模式：点击“下载任务开始”后，由后端直接调用 <code>yt-dlp</code> 下载到
        <code>pre-run/storage/downloads/manual/</code>。
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
});

const onUrlInput = (event) => {
  props.downloadForm.url = event.target.value;
};

const onAudioOnlyChange = (event) => {
  const next = String(event.target.value || "false").toLowerCase() === "true";
  props.downloadForm.audioOnly = next;
  if (next && !["mp3", "m4a", "wav", "flac"].includes(String(props.downloadForm.outputFormat || "").toLowerCase())) {
    props.downloadForm.outputFormat = "mp3";
  }
};

const onFormatChange = (event) => {
  const next = String(event.target.value || "mp4").toLowerCase();
  props.downloadForm.outputFormat = next;
  if (["mp3", "m4a", "wav", "flac"].includes(next)) {
    props.downloadForm.audioOnly = true;
  }
};
</script>
