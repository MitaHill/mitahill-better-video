<template>
  <div class="param-group">
    <div class="param-section">
      <div class="param-title">视频下载来源</div>
      <div class="field">
        <label>视频链接（支持批量，一行一个）</label>
        <textarea
          :value="downloadForm.sourceUrl"
          rows="4"
          placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=..."
          @input="onUrlInput"
        ></textarea>
      </div>

      <div class="status-row" style="gap: 8px;">
        <button type="button" class="secondary" :disabled="downloadForm.probeLoading" @click="onProbeSource">
          {{ downloadForm.probeLoading ? "解析中..." : "解析清晰度与字幕" }}
        </button>
        <span class="notice" v-if="downloadForm.maxQualityLabel">
          免登录可用最高：{{ downloadForm.maxQualityLabel }}
        </span>
      </div>
      <div class="field compact">
        <label>Cookie 文件（可选）</label>
        <div class="file-picker-row">
          <input ref="cookieInput" class="file-input-hidden" type="file" accept=".txt,text/plain" @change="onCookieFileChange" />
          <button type="button" class="secondary" @click="openCookiePicker">
            {{ downloadForm.cookieFile ? "重新选择 Cookie" : "选择 Cookie" }}
          </button>
          <span v-if="downloadForm.cookieFile" class="selected-file-count">{{ downloadForm.cookieFile.name }}</span>
        </div>
        <p class="notice">用于需要登录态的视频解析与下载。上传后会持久保存，之后默认复用；再次选择文件会覆盖旧 Cookie。</p>
      </div>
      <p v-if="downloadForm.probeError" class="notice" style="color: var(--accent-2);">{{ downloadForm.probeError }}</p>
      <p v-if="downloadForm.probeMessage" class="notice">{{ downloadForm.probeMessage }}</p>
      <p v-if="downloadForm.probeReady" class="notice">
        源信息：{{ resolveSourceSummary() }}
      </p>

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
import { ref } from "vue";

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

const cookieInput = ref(null);

const openCookiePicker = () => {
  cookieInput.value?.click();
};

const onCookieFileChange = (event) => {
  const file = Array.from(event.target.files || [])[0] || null;
  props.downloadForm.cookieFile = file;
  props.downloadForm.probeReady = false;
  props.downloadForm.probeMessage = file ? `已选择 Cookie：${file.name}，解析或创建任务时会更新服务器 Cookie。` : "";
  event.target.value = "";
};

const onUrlInput = (event) => {
  props.downloadForm.sourceUrl = event.target.value;
  props.downloadForm.probeReady = false;
};

const onProbeSource = () => {
  if (typeof props.onProbeSource === "function") {
    props.onProbeSource();
  }
};

const onModeChange = (event) => {
  props.downloadForm.downloadMode = String(event.target.value || "video");
  props.downloadForm.sourceWidth = Number(props.downloadForm.probeWidth || 0);
  props.downloadForm.sourceHeight = Number(props.downloadForm.probeHeight || 0);
  props.downloadForm.sourceFps = Number(props.downloadForm.probeFps || 0);
  props.downloadForm.sourceSizeMb = Number(props.downloadForm.probeSizeMb || 0);
};

const onQualityChange = (event) => {
  props.downloadForm.qualitySelector = String(event.target.value || "bestvideo*+bestaudio/best");
  const selected = Array.isArray(props.downloadForm.qualityOptions)
    ? props.downloadForm.qualityOptions.find((item) => item.value === props.downloadForm.qualitySelector)
    : null;
  props.downloadForm.sourceWidth = Number(selected?.width || props.downloadForm.probeWidth || 0);
  props.downloadForm.sourceHeight = Number(selected?.height || props.downloadForm.probeHeight || 0);
  props.downloadForm.sourceFps = Number(selected?.fps || props.downloadForm.probeFps || 0);
  props.downloadForm.sourceSizeMb = Number(selected?.size_mb || props.downloadForm.probeSizeMb || 0);
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

const resolveSourceSummary = () => {
  const width = Number(props.downloadForm.sourceWidth || 0);
  const height = Number(props.downloadForm.sourceHeight || 0);
  const fps = Number(props.downloadForm.sourceFps || 0);
  const sizeMb = Number(props.downloadForm.sourceSizeMb || 0);
  const resolution = width && height ? `${width}x${height}` : "分辨率待定";
  const fpsText = fps > 0 ? ` | ${Math.round(fps * 100) / 100}fps` : "";
  const sizeText = sizeMb > 0 ? ` | 约 ${sizeMb.toFixed(2)} MB` : "";
  return `${resolution}${fpsText}${sizeText}`;
};
</script>
