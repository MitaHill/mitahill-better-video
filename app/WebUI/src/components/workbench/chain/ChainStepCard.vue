<template>
  <div
    class="chain-step"
    draggable="true"
    @dragstart="onDragStart(index)"
    @dragover="onDragOver"
    @drop="onDrop(index)"
  >
    <div class="chain-step-head">
      <span class="chain-step-handle" title="按住拖拽调整顺序">⣿ 第 {{ index + 1 }} 步</span>
      <select :value="step.category" @change="onCategoryChange">
        <option v-for="item in categoryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
      <button type="button" class="secondary" @click="removeStep(index)">删除</button>
    </div>

    <div class="param-group">
      <template v-if="step.category === 'enhance'">
        <EnhanceBaseSection
          :enhance-form="step.state.enhanceForm"
          :get-field-policy="getFieldPolicy"
          :show-source-picker="false"
        />
        <EnhanceVisualSection :enhance-form="step.state.enhanceForm" :get-field-policy="getFieldPolicy" />
        <EnhanceEncodeSection :enhance-form="step.state.enhanceForm" :get-field-policy="getFieldPolicy" />
      </template>

      <template v-else-if="step.category === 'convert'">
        <ConvertBaseSection
          :convert-form="step.state.convertForm"
          :get-field-policy="getFieldPolicy"
          :show-source-picker="false"
        />
        <ConvertVideoSection :convert-form="step.state.convertForm" :get-field-policy="getFieldPolicy" />
        <ConvertExportFramesSection
          v-if="step.state.convertForm.convertMode === 'export_frames'"
          :convert-form="step.state.convertForm"
          :get-field-policy="getFieldPolicy"
        />
      </template>

      <template v-else>
        <TranscribeBaseSection
          :transcribe-form="step.state.transcribeForm"
          :get-field-policy="getFieldPolicy"
          :runtime-config="transcriptionRuntimeConfig"
          :show-source-picker="false"
        />
        <TranscribeTranslationSection
          :transcribe-form="step.state.transcribeForm"
          :get-field-policy="getFieldPolicy"
          :runtime-config="transcriptionRuntimeConfig"
        />
        <TranscribeAdvancedSection :transcribe-form="step.state.transcribeForm" :get-field-policy="getFieldPolicy" />
      </template>
    </div>
  </div>
</template>

<script setup>
import ConvertBaseSection from "../convert/ConvertBaseSection.vue";
import ConvertExportFramesSection from "../convert/ConvertExportFramesSection.vue";
import ConvertVideoSection from "../convert/ConvertVideoSection.vue";
import EnhanceBaseSection from "../enhance/EnhanceBaseSection.vue";
import EnhanceEncodeSection from "../enhance/EnhanceEncodeSection.vue";
import EnhanceVisualSection from "../enhance/EnhanceVisualSection.vue";
import TranscribeAdvancedSection from "../transcribe/TranscribeAdvancedSection.vue";
import TranscribeBaseSection from "../transcribe/TranscribeBaseSection.vue";
import TranscribeTranslationSection from "../transcribe/TranscribeTranslationSection.vue";

const props = defineProps({
  step: {
    type: Object,
    required: true,
  },
  index: {
    type: Number,
    required: true,
  },
  categoryOptions: {
    type: Array,
    required: true,
  },
  getFieldPolicy: {
    type: Function,
    required: true,
  },
  transcriptionRuntimeConfig: {
    type: Object,
    default: null,
  },
  setStepCategory: {
    type: Function,
    required: true,
  },
  removeStep: {
    type: Function,
    required: true,
  },
  onDragStart: {
    type: Function,
    required: true,
  },
  onDragOver: {
    type: Function,
    required: true,
  },
  onDrop: {
    type: Function,
    required: true,
  },
});

const onCategoryChange = (event) => {
  props.setStepCategory(props.index, event.target.value);
};
</script>

<style scoped>
.chain-step {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}

.chain-step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.chain-step-handle {
  cursor: grab;
  font-weight: 600;
  white-space: nowrap;
}

.chain-step-head select {
  flex: 1;
}
</style>
