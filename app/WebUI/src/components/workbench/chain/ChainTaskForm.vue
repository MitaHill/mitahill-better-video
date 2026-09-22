<template>
  <div class="param-group">
    <div class="param-section">
      <div class="param-title">链输入</div>
      <div class="field">
        <label>上传文件（一条链只处理一个文件）</label>
        <input ref="fileInput" class="file-input-hidden" type="file" @change="chain.onChainFileChange" />
        <div class="file-picker-row">
          <button type="button" class="secondary" @click="openFilePicker">
            {{ chain.chainFiles.length ? "重新选择文件" : "选择文件" }}
          </button>
          <span v-if="chain.chainFiles.length" class="selected-file-count">{{ chain.chainFiles[0].name }}</span>
        </div>
      </div>
      <p class="notice">
        每一步的产物直接交给下一步。步骤串行执行，不会并行；转录产出字幕，只能放在最后一步。
      </p>
    </div>

    <ChainStepCard
      v-for="(step, index) in chain.chainSteps"
      :key="step.id"
      :step="step"
      :index="index"
      :category-options="categoryOptions"
      :get-field-policy="getFieldPolicy"
      :transcription-runtime-config="transcriptionRuntimeConfig"
      :set-step-category="chain.setStepCategory"
      :remove-step="chain.removeStep"
      :on-drag-start="chain.onDragStart"
      :on-drag-over="chain.onDragOver"
      :on-drop="chain.onDrop"
    />

    <div class="chain-add-row">
      <button
        type="button"
        class="secondary"
        :disabled="chain.chainSteps.length >= maxSteps"
        @click="chain.addStep('enhance')"
      >
        添加步骤
      </button>
      <span class="notice">{{ chain.chainSteps.length }} / {{ maxSteps }} 步</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import ChainStepCard from "./ChainStepCard.vue";
import { CHAIN_CATEGORY_OPTIONS, CHAIN_MAX_STEPS } from "../../../composables/workbench/useTaskChain";

defineProps({
  chain: {
    type: Object,
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
});

const fileInput = ref(null);
const categoryOptions = CHAIN_CATEGORY_OPTIONS;
const maxSteps = CHAIN_MAX_STEPS;

const openFilePicker = () => {
  fileInput.value?.click();
};
</script>

<style scoped>
.chain-add-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
