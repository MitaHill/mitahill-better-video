<template>
  <div class="app-shell">
    <WorkbenchHeader
      :theme-mode="themeMode"
      :active-category="activeCategory"
      @update:theme-mode="onThemeModeChange"
      @switch-category="switchCategory"
    />

    <section class="panel-grid">
      <template v-if="activeCategory !== 'admin'">
        <TaskCreatePanel
          :active-category="activeCategory"
          :enhance-form="enhanceForm"
          :convert-form="convertForm"
          :convert-media-info="convertMediaInfo"
          :transcribe-form="transcribeForm"
          :transcribe-media-info="transcribeMediaInfo"
          :transcribe-runtime="transcribeRuntime"
          :download-form="downloadForm"
          :loading-submit="loading.submit"
          :submit-error="submitError"
          :submit-warnings="submitWarnings"
          :on-enhance-file-change="onEnhanceFileChange"
          :on-convert-media-change="onConvertMediaChange"
          :on-transcribe-media-change="onTranscribeMediaChange"
          :on-watermark-images-change="onWatermarkImagesChange"
          :on-watermark-lua-file-change="onWatermarkLuaFileChange"
          :on-probe-download-source="probeDownloadSource"
          :add-watermark-segment="addWatermarkSegment"
          :remove-watermark-segment="removeWatermarkSegment"
          :get-field-policy="getFieldPolicy"
          :submit-task="submitTask"
        />

        <TaskStatusPanel
          :status-query="statusQuery"
          :status="status"
          :status-class="statusClass"
          :progress-details="progressDetails"
          :translation-progress-text="translationProgressText"
          :stream-lines="streamLines"
          :resolution="resolution"
          :task-ids="taskIds"
          :preview="preview"
          :is-preview-supported="isPreviewSupported"
          :param-rows="paramRows"
          :status-error="statusError"
          :fetch-status="fetchStatus"
          :download-result="downloadResult"
          @update:status-query="setStatusQuery"
        />
      </template>

      <template v-else>
        <AdminPanel :active="activeCategory === 'admin'" />
      </template>
    </section>

    <div class="app-signature">由CodeX和米塔山开发</div>
  </div>
</template>

<script setup>
import TaskCreatePanel from "../components/workbench/TaskCreatePanel.vue";
import TaskStatusPanel from "../components/workbench/TaskStatusPanel.vue";
import WorkbenchHeader from "../components/workbench/WorkbenchHeader.vue";
import AdminPanel from "../components/admin/AdminPanel.vue";
import { useWorkbenchController } from "../composables/useWorkbenchController";

const {
  activeCategory,
  themeMode,
  enhanceForm,
  convertForm,
  convertMediaInfo,
  transcribeForm,
  transcribeMediaInfo,
  transcribeRuntime,
  downloadForm,
  taskIds,
  submitError,
  submitWarnings,
  statusQuery,
  status,
  statusError,
  loading,
  preview,
  isPreviewSupported,
  resolution,
  paramRows,
  statusClass,
  progressDetails,
  translationProgressText,
  streamLines,
  onEnhanceFileChange,
  onConvertMediaChange,
  onTranscribeMediaChange,
  onWatermarkImagesChange,
  onWatermarkLuaFileChange,
  probeDownloadSource,
  addWatermarkSegment,
  removeWatermarkSegment,
  getFieldPolicy,
  submitTask,
  fetchStatus,
  downloadResult,
  onThemeModeChange,
  switchCategory,
  setStatusQuery,
} = useWorkbenchController();
</script>
