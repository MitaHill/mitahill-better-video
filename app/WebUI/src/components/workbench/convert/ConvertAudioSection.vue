<template>
  <div class="param-section" v-if="convertForm.convertMode === 'transcode'">
    <div class="param-title">音频参数</div>
    <div class="field">
      <label>音频来源</label>
      <select v-model="convertForm.audioSourceMode" :disabled="convertForm.muteAudio || isDisabled('audioSourceMode')">
        <option v-for="item in audioSourceModeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>声道</label><select v-model="convertForm.audioChannelsMode" :disabled="convertForm.muteAudio || isDisabled('audioChannelsMode')"><option v-for="item in audioChannelsOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></div>
      <div class="field compact"><label>采样率(Hz)</label><input v-model.number="convertForm.audioSampleRate" type="number" :min="numMin('audioSampleRate', 0)" :max="numMax('audioSampleRate', 192000)" :step="numStep('audioSampleRate', 1)" placeholder="0=自动" :disabled="convertForm.muteAudio || isDisabled('audioSampleRate')" /></div>
      <div class="field compact"><label>音频码率(kbps)</label><input v-model.number="convertForm.audioBitrateK" type="number" :min="numMin('audioBitrateK', 32)" :max="numMax('audioBitrateK', 1024)" :step="numStep('audioBitrateK', 1)" :disabled="convertForm.muteAudio || isDisabled('audioBitrateK')" /></div>
    </div>
    <div class="inline-grid four">
      <div class="field compact"><label>音量倍率</label><input v-model.number="convertForm.audioVolume" type="number" :min="numMin('audioVolume', 0)" :max="numMax('audioVolume', 5)" :step="numStep('audioVolume', 0.1)" :disabled="convertForm.muteAudio || isDisabled('audioVolume')" /></div>
      <div class="field compact"><label>音频淡入(秒)</label><input v-model.number="convertForm.audioFadeInSec" type="number" :min="numMin('audioFadeInSec', 0)" :max="numMax('audioFadeInSec', 30)" :step="numStep('audioFadeInSec', 0.1)" :disabled="convertForm.muteAudio || isDisabled('audioFadeInSec')" /></div>
      <div class="field compact"><label>音频淡出(秒)</label><input v-model.number="convertForm.audioFadeOutSec" type="number" :min="numMin('audioFadeOutSec', 0)" :max="numMax('audioFadeOutSec', 30)" :step="numStep('audioFadeOutSec', 0.1)" :disabled="convertForm.muteAudio || isDisabled('audioFadeOutSec')" /></div>
      <div class="field compact"><label>哈斯延迟(ms)</label><input v-model.number="convertForm.haasDelayMs" type="number" :min="numMin('haasDelayMs', 0)" :max="numMax('haasDelayMs', 3000)" :step="numStep('haasDelayMs', 1)" :disabled="convertForm.muteAudio || !convertForm.haasEnabled || isDisabled('haasDelayMs')" /></div>
    </div>
    <div class="inline-grid four">
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioEcho" :disabled="convertForm.muteAudio || isDisabled('audioEcho')" />回声</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioDenoise" :disabled="convertForm.muteAudio || isDisabled('audioDenoise')" />降噪</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.audioReverse" :disabled="convertForm.muteAudio || isDisabled('audioReverse')" />反向</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.haasEnabled" :disabled="convertForm.muteAudio || isDisabled('haasEnabled')" />哈斯效应</label>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>回声延迟(ms)</label><input v-model.number="convertForm.audioEchoDelayMs" type="number" :min="numMin('audioEchoDelayMs', 1)" :max="numMax('audioEchoDelayMs', 3000)" :step="numStep('audioEchoDelayMs', 1)" :disabled="!convertForm.audioEcho || convertForm.muteAudio || isDisabled('audioEchoDelayMs')" /></div>
      <div class="field compact"><label>回声衰减</label><input v-model.number="convertForm.audioEchoDecay" type="number" :min="numMin('audioEchoDecay', 0)" :max="numMax('audioEchoDecay', 1)" :step="numStep('audioEchoDecay', 0.05)" :disabled="!convertForm.audioEcho || convertForm.muteAudio || isDisabled('audioEchoDecay')" /></div>
      <div class="field compact"><label>哈斯声道先行</label><select v-model="convertForm.haasLead" :disabled="!convertForm.haasEnabled || convertForm.muteAudio || isDisabled('haasLead')"><option v-for="item in haasLeadOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
});

const readPolicy = (fieldKey) => props.getFieldPolicy("convert", fieldKey) || null;
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

const audioSourceModeOptions = computed(() =>
  allowed("audioSourceMode", ["keep_original", "replace_uploaded", "mix_uploaded"]).map((value) => ({
    value,
    label:
      value === "keep_original"
        ? "保留原视频音轨"
        : value === "replace_uploaded"
          ? "使用上传音频替换"
          : value === "mix_uploaded"
            ? "原音 + 上传音频混合"
            : value,
  }))
);

const audioChannelsOptions = computed(() =>
  allowed("audioChannelsMode", ["keep", "mono", "stereo"]).map((value) => ({
    value,
    label: value === "keep" ? "保持原始" : value === "mono" ? "单声道" : value === "stereo" ? "双声道" : value,
  }))
);

const haasLeadOptions = computed(() =>
  allowed("haasLead", ["left", "right"]).map((value) => ({
    value,
    label: value === "left" ? "左声道先出声" : value === "right" ? "右声道先出声" : value,
  }))
);
</script>
