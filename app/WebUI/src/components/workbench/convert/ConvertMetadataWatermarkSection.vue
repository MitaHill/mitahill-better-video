<template>
  <div class="param-section" v-if="convertForm.convertMode === 'transcode'">
    <div class="param-title">元数据与水印</div>
    <div class="inline-grid three">
      <div class="field compact"><label>标题</label><input v-model="convertForm.metaTitle" placeholder="可选" /></div>
      <div class="field compact"><label>作者</label><input v-model="convertForm.metaAuthor" placeholder="可选" /></div>
      <div class="field compact"><label>注释</label><input v-model="convertForm.metaComment" placeholder="可选" /></div>
    </div>
    <div class="inline-grid two">
      <label class="check-inline"><input type="checkbox" v-model="convertForm.watermarkEnableText" />启用文字水印</label>
      <label class="check-inline"><input type="checkbox" v-model="convertForm.watermarkEnableImage" />启用图片水印</label>
    </div>
    <div class="field" v-if="convertForm.watermarkEnableText">
      <label>默认文字水印（当分段未填写文本时使用）</label>
      <input v-model="convertForm.watermarkDefaultText" placeholder="例如：MitaHill" />
    </div>
    <div class="inline-grid two">
      <div class="field compact"><label>默认透明度 (0.05~1)</label><input v-model.number="convertForm.watermarkAlpha" type="number" min="0.05" max="1" step="0.05" /></div>
      <div class="field compact"><label>图片水印文件（可多个）</label><input type="file" accept="image/*" multiple @change="onWatermarkImagesChange" /></div>
    </div>

    <WatermarkTimelineEditor
      :convert-form="convertForm"
      :add-watermark-segment="addWatermarkSegment"
      :remove-watermark-segment="removeWatermarkSegment"
      :on-watermark-lua-file-change="onWatermarkLuaFileChange"
    />
  </div>
</template>

<script setup>
import WatermarkTimelineEditor from "../WatermarkTimelineEditor.vue";

defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  onWatermarkImagesChange: {
    type: Function,
    required: true,
  },
  onWatermarkLuaFileChange: {
    type: Function,
    required: true,
  },
  addWatermarkSegment: {
    type: Function,
    required: true,
  },
  removeWatermarkSegment: {
    type: Function,
    required: true,
  },
});
</script>
