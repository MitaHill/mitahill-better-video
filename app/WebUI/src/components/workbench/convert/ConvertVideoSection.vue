<template>
  <div class="param-section" v-if="convertForm.convertMode === 'transcode'">
    <div class="param-title">视频参数</div>
    <div class="inline-grid three">
      <div class="field compact">
        <label>格式</label>
        <select v-model="convertForm.outputFormat">
          <option value="mp4">MP4</option>
          <option value="mkv">MKV</option>
          <option value="mov">MOV</option>
          <option value="avi">AVI</option>
        </select>
      </div>
      <div class="field compact">
        <label>编码</label>
        <select v-model="convertForm.videoCodec">
          <option value="h264">H264</option>
          <option value="h265">H265</option>
        </select>
      </div>
      <div class="field compact">
        <label>帧率</label>
        <input v-model.number="convertForm.frameRate" type="number" min="0" max="120" placeholder="0=保持" />
      </div>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>CRF</label><input v-model.number="convertForm.crf" type="number" min="10" max="35" /></div>
      <div class="field compact"><label>码率(kbps)</label><input v-model.number="convertForm.videoBitrateK" type="number" min="0" placeholder="0=自动" /></div>
      <div class="field compact"><label>大小限制(MB)</label><input v-model.number="convertForm.targetSizeMb" type="number" min="0" step="0.1" /></div>
    </div>
    <div class="inline-grid four">
      <div class="field compact"><label>宽</label><input v-model.number="convertForm.targetWidth" type="number" min="0" placeholder="0=保持" /></div>
      <div class="field compact"><label>高</label><input v-model.number="convertForm.targetHeight" type="number" min="0" placeholder="0=保持" /></div>
      <div class="field compact">
        <label>宽高比</label>
        <select v-model="convertForm.aspectRatio">
          <option value="">保持原始</option>
          <option value="16/9">16:9</option>
          <option value="4/3">4:3</option>
          <option value="1/1">1:1</option>
          <option value="9/16">9:16</option>
        </select>
      </div>
      <div class="field compact"><label>二次编码</label><select v-model="convertForm.secondPassReencode"><option :value="false">关闭</option><option :value="true">启用</option></select></div>
    </div>
    <div class="inline-grid four">
      <label class="check-inline"><input type="checkbox" v-model="convertForm.deinterlace" />反交错</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.flipHorizontal" />左右颠倒</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.flipVertical" />上下颠倒</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.muteAudio" />关闭声音</label>
    </div>
    <div class="inline-grid two">
      <div class="field compact"><label>视频淡入(秒)</label><input v-model.number="convertForm.videoFadeInSec" type="number" min="0" max="30" step="0.1" /></div>
      <div class="field compact"><label>视频淡出(秒)</label><input v-model.number="convertForm.videoFadeOutSec" type="number" min="0" max="30" step="0.1" /></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
});
</script>
