<template>
  <div class="param-section" v-if="convertForm.convertMode === 'transcode'">
    <div class="param-title">视频参数</div>
    <div class="inline-grid three">
      <div class="field compact">
        <label>格式</label>
        <select v-model="convertForm.outputFormat" :disabled="isDisabled('outputFormat')">
          <option v-for="item in outputFormatOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>编码</label>
        <select v-model="convertForm.videoCodec" :disabled="isDisabled('videoCodec')">
          <option v-for="item in videoCodecOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact">
        <label>帧率</label>
        <input
          v-model.number="convertForm.frameRate"
          type="number"
          :min="numMin('frameRate', 0)"
          :max="numMax('frameRate', 120)"
          :step="numStep('frameRate', 1)"
          :disabled="isDisabled('frameRate')"
          placeholder="0=保持"
        />
      </div>
    </div>
    <div class="inline-grid three">
      <div class="field compact"><label>CRF</label><input v-model.number="convertForm.crf" type="number" :min="numMin('crf', 10)" :max="numMax('crf', 35)" :step="numStep('crf', 1)" :disabled="isDisabled('crf')" /></div>
      <div class="field compact"><label>码率(kbps)</label><input v-model.number="convertForm.videoBitrateK" type="number" :min="numMin('videoBitrateK', 0)" :max="numMax('videoBitrateK', 200000)" :step="numStep('videoBitrateK', 1)" :disabled="isDisabled('videoBitrateK')" placeholder="0=自动" /></div>
      <div class="field compact"><label>大小限制(MB)</label><input v-model.number="convertForm.targetSizeMb" type="number" :min="numMin('targetSizeMb', 0)" :max="numMax('targetSizeMb', 102400)" :step="numStep('targetSizeMb', 0.1)" :disabled="isDisabled('targetSizeMb')" /></div>
    </div>
    <div class="inline-grid four">
      <div class="field compact"><label>宽</label><input v-model.number="convertForm.targetWidth" type="number" :min="numMin('targetWidth', 0)" :max="numMax('targetWidth', 16384)" :step="numStep('targetWidth', 1)" :disabled="isDisabled('targetWidth')" placeholder="0=保持" /></div>
      <div class="field compact"><label>高</label><input v-model.number="convertForm.targetHeight" type="number" :min="numMin('targetHeight', 0)" :max="numMax('targetHeight', 16384)" :step="numStep('targetHeight', 1)" :disabled="isDisabled('targetHeight')" placeholder="0=保持" /></div>
      <div class="field compact">
        <label>宽高比</label>
        <select v-model="convertForm.aspectRatio" :disabled="isDisabled('aspectRatio')">
          <option v-for="item in aspectRatioOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </div>
      <div class="field compact"><label>二次编码</label><select v-model="convertForm.secondPassReencode" :disabled="isDisabled('secondPassReencode')"><option :value="false">关闭</option><option :value="true">启用</option></select></div>
    </div>
    <div class="inline-grid four">
      <label class="check-inline"><input type="checkbox" v-model="convertForm.deinterlace" :disabled="isDisabled('deinterlace')" />反交错</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.flipHorizontal" :disabled="isDisabled('flipHorizontal')" />左右颠倒</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.flipVertical" :disabled="isDisabled('flipVertical')" />上下颠倒</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.muteAudio" :disabled="isDisabled('muteAudio')" />关闭声音</label>
    </div>
    <div class="inline-grid two">
      <div class="field compact"><label>视频淡入(秒)</label><input v-model.number="convertForm.videoFadeInSec" type="number" :min="numMin('videoFadeInSec', 0)" :max="numMax('videoFadeInSec', 30)" :step="numStep('videoFadeInSec', 0.1)" :disabled="isDisabled('videoFadeInSec')" /></div>
      <div class="field compact"><label>视频淡出(秒)</label><input v-model.number="convertForm.videoFadeOutSec" type="number" :min="numMin('videoFadeOutSec', 0)" :max="numMax('videoFadeOutSec', 30)" :step="numStep('videoFadeOutSec', 0.1)" :disabled="isDisabled('videoFadeOutSec')" /></div>
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

const outputFormatOptions = computed(() =>
  allowed("outputFormat", ["mp4", "mkv", "mov", "avi"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);

const videoCodecOptions = computed(() =>
  allowed("videoCodec", ["h264", "h265"]).map((value) => ({
    value,
    label: String(value || "").toUpperCase(),
  }))
);

const aspectRatioOptions = computed(() =>
  allowed("aspectRatio", ["", "16/9", "4/3", "1/1", "9/16"]).map((value) => ({
    value,
    label: value ? value.replace("/", ":") : "保持原始",
  }))
);
</script>
