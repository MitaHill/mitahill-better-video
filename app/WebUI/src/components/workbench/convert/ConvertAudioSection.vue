<template>
  <div class="param-section" v-if="convertForm.convertMode === 'transcode'">
    <div class="param-title">音频参数</div>
    <div class="field">
      <label>音频来源</label>
      <select v-model="convertForm.audioSourceMode" :disabled="convertForm.muteAudio">
        <option value="keep_original">保留原视频音轨</option>
        <option value="replace_uploaded">使用上传音频替换</option>
        <option value="mix_uploaded">原音 + 上传音频混合</option>
      </select>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>声道</label><select v-model="convertForm.audioChannelsMode" :disabled="convertForm.muteAudio"><option value="keep">保持原始</option><option value="mono">单声道</option><option value="stereo">双声道</option></select></div>
      <div class="field compact"><label>采样率(Hz)</label><input v-model.number="convertForm.audioSampleRate" type="number" min="0" placeholder="0=自动" :disabled="convertForm.muteAudio" /></div>
      <div class="field compact"><label>音频码率(kbps)</label><input v-model.number="convertForm.audioBitrateK" type="number" min="32" max="1024" :disabled="convertForm.muteAudio" /></div>
    </div>
    <div class="inline-grid four">
      <div class="field compact"><label>音量倍率</label><input v-model.number="convertForm.audioVolume" type="number" min="0" max="5" step="0.1" :disabled="convertForm.muteAudio" /></div>
      <div class="field compact"><label>音频淡入(秒)</label><input v-model.number="convertForm.audioFadeInSec" type="number" min="0" max="30" step="0.1" :disabled="convertForm.muteAudio" /></div>
      <div class="field compact"><label>音频淡出(秒)</label><input v-model.number="convertForm.audioFadeOutSec" type="number" min="0" max="30" step="0.1" :disabled="convertForm.muteAudio" /></div>
      <div class="field compact"><label>哈斯延迟(ms)</label><input v-model.number="convertForm.haasDelayMs" type="number" min="0" max="3000" :disabled="convertForm.muteAudio || !convertForm.haasEnabled" /></div>
    </div>
    <div class="inline-grid four">
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioEcho" :disabled="convertForm.muteAudio" />回声</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioDenoise" :disabled="convertForm.muteAudio" />降噪</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioReverse" :disabled="convertForm.muteAudio" />反向</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.haasEnabled" :disabled="convertForm.muteAudio" />哈斯效应</label>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>回声延迟(ms)</label><input v-model.number="convertForm.audioEchoDelayMs" type="number" min="1" max="3000" :disabled="!convertForm.audioEcho || convertForm.muteAudio" /></div>
      <div class="field compact"><label>回声衰减</label><input v-model.number="convertForm.audioEchoDecay" type="number" min="0" max="1" step="0.05" :disabled="!convertForm.audioEcho || convertForm.muteAudio" /></div>
      <div class="field compact"><label>哈斯声道先行</label><select v-model="convertForm.haasLead" :disabled="!convertForm.haasEnabled || convertForm.muteAudio"><option value="left">左声道先出声</option><option value="right">右声道先出声</option></select></div>
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
