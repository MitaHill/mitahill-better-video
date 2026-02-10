<template>
  <div class="param-group">
    <ConvertBaseSection
      :convert-form="convertForm"
      :convert-media-info="convertMediaInfo"
      :on-convert-media-change="onConvertMediaChange"
    />

    <ConvertVideoSection :convert-form="convertForm" />
    <ConvertAudioSection :convert-form="convertForm" />

    <ConvertMetadataWatermarkSection
      :convert-form="convertForm"
      :on-watermark-images-change="onWatermarkImagesChange"
      :on-watermark-lua-file-change="onWatermarkLuaFileChange"
      :add-watermark-segment="addWatermarkSegment"
      :remove-watermark-segment="removeWatermarkSegment"
    />

    <ConvertExportFramesSection :convert-form="convertForm" />
  </div>
</template>

<script setup>
import ConvertAudioSection from "./convert/ConvertAudioSection.vue";
import ConvertBaseSection from "./convert/ConvertBaseSection.vue";
import ConvertExportFramesSection from "./convert/ConvertExportFramesSection.vue";
import ConvertMetadataWatermarkSection from "./convert/ConvertMetadataWatermarkSection.vue";
import ConvertVideoSection from "./convert/ConvertVideoSection.vue";

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
