<template>
  <div class="param-section">
    <div class="param-title">任务基础</div>
    <div class="field">
      <label>转换类型</label>
      <select v-model="convertForm.convertMode">
        <option value="transcode">视频转换</option>
        <option value="export_frames">导出视频帧（批量 ZIP）</option>
        <option value="demux_streams">分离画面流和音频流（批量 ZIP）</option>
      </select>
    </div>
    <div class="field">
      <label>上传音频或视频（可多选）</label>
      <input type="file" multiple accept="video/*,audio/*" @change="onConvertMediaChange" />
    </div>
    <div class="media-list" v-if="convertMediaInfo.length">
      <div class="media-row" v-for="item in convertMediaInfo" :key="item.filename + ':' + item.size_mb">
        <span>{{ item.filename }}</span>
        <span>{{ item.has_video ? '视频' : (item.has_audio ? '音频' : '未知') }}</span>
        <span v-if="item.fps">{{ item.fps }} fps</span>
        <span v-if="item.video_codec">{{ item.video_codec.toUpperCase() }}</span>
        <span v-if="item.audio_sample_rate">{{ item.audio_sample_rate }} Hz</span>
        <span v-if="item.audio_bitrate">{{ Math.round(item.audio_bitrate / 1000) }} kbps</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  convertMediaInfo: {
    type: Array,
    required: true,
  },
  onConvertMediaChange: {
    type: Function,
    required: true,
  },
});
</script>
