<template>
  <div class="app-shell">
    <WorkbenchHeader
      :theme-mode="themeMode"
      :active-category="activeCategory"
      @update:theme-mode="onThemeModeChange"
      @switch-category="switchCategory"
    />

    <section class="panel-grid">
      <TaskCreatePanel
        :active-category="activeCategory"
        :enhance-form="enhanceForm"
        :convert-form="convertForm"
        :convert-media-info="convertMediaInfo"
        :loading-submit="loading.submit"
        :submit-error="submitError"
        :submit-warnings="submitWarnings"
        :on-enhance-file-change="onEnhanceFileChange"
        :on-convert-media-change="onConvertMediaChange"
        :on-watermark-images-change="onWatermarkImagesChange"
        :on-watermark-lua-file-change="onWatermarkLuaFileChange"
        :add-watermark-segment="addWatermarkSegment"
        :remove-watermark-segment="removeWatermarkSegment"
        :submit-task="submitTask"
      />

      <TaskStatusPanel
        :status-query="statusQuery"
        :status="status"
        :status-class="statusClass"
        :progress-details="progressDetails"
        :resolution="resolution"
        :task-ids="taskIds"
        :preview="preview"
        :is-conversion-task="isConversionTask"
        :param-rows="paramRows"
        :status-error="statusError"
        :fetch-status="fetchStatus"
        :download-result="downloadResult"
        @update:status-query="setStatusQuery"
      />
    </section>

    <div class="app-signature">由CodeX和米塔山开发</div>
  </div>
</template>

<script setup>
import TaskCreatePanel from "../components/workbench/TaskCreatePanel.vue";
import TaskStatusPanel from "../components/workbench/TaskStatusPanel.vue";
import WorkbenchHeader from "../components/workbench/WorkbenchHeader.vue";
import { useWorkbenchController } from "../composables/useWorkbenchController";

const {
  activeCategory,
  themeMode,
  enhanceForm,
  convertForm,
  convertMediaInfo,
  taskIds,
  submitError,
  submitWarnings,
  statusQuery,
  status,
  statusError,
  loading,
  preview,
  isConversionTask,
  resolution,
  paramRows,
  statusClass,
  progressDetails,
  onEnhanceFileChange,
  onConvertMediaChange,
  onWatermarkImagesChange,
  onWatermarkLuaFileChange,
  addWatermarkSegment,
  removeWatermarkSegment,
  submitTask,
  fetchStatus,
  downloadResult,
  onThemeModeChange,
  switchCategory,
  setStatusQuery,
} = useWorkbenchController();
</script>
