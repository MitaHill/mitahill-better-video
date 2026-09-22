import { onMounted, onUnmounted, reactive, ref } from "vue";
import { useWorkbenchCategory } from "./workbench/useWorkbenchCategory";
import { useWorkbenchFormsState } from "./workbench/useWorkbenchFormsState";
import { useWorkbenchRecommendations } from "./workbench/useWorkbenchRecommendations";
import { useWorkbenchFormConstraints } from "./workbench/useWorkbenchFormConstraints";
import { useWorkbenchStatus } from "./workbench/useWorkbenchStatus";
import { useWorkbenchSubmission } from "./workbench/useWorkbenchSubmission";
import { useWorkbenchTheme } from "./workbench/useWorkbenchTheme";
import { useTranscribeLowDataMode } from "./workbench/useTranscribeLowDataMode";
import { useWorkbenchUploads } from "./workbench/useWorkbenchUploads";
import { useTaskChain } from "./workbench/useTaskChain";
import { parseJsonSafe } from "./workbench/utils";

export const useWorkbenchController = () => {
  const loading = reactive({ submit: false });
  const submitError = ref("");
  const submitWarnings = ref("");
  const transcriptionRuntimeConfig = ref(null);

  const { themeMode, activeTheme, onThemeModeChange, initTheme, disposeTheme } = useWorkbenchTheme();
  const { activeCategory, switchCategory, initCategoryRouting, disposeCategoryRouting } = useWorkbenchCategory();

  const {
    enhanceForm,
    convertForm,
    convertMediaInfo,
    transcribeForm,
    transcribeMediaInfo,
    addWatermarkSegment,
    removeWatermarkSegment,
  } = useWorkbenchFormsState();

  const {
    constraints,
    status: constraintsStatus,
    fetchConstraints,
    getFieldPolicy,
    enforceCategory,
  } = useWorkbenchFormConstraints({
    parseJsonSafe,
    enhanceForm,
    convertForm,
    transcribeForm,
  });

  const {
    taskIds,
    statusQuery,
    status,
    statusError,
    preview,
    live,
    isPreviewSupported,
    resolution,
    paramRows,
    statusClass,
    progressDetails,
    fetchStatus,
    downloadResult,
    joinRoom,
    setStatusQuery,
    initRealtime,
    disposeRealtime,
  } = useWorkbenchStatus({ parseJsonSafe });

  const { onEnhanceFileChange, onConvertMediaChange, onTranscribeMediaChange, onWatermarkImagesChange } = useWorkbenchUploads({
    enhanceForm,
    convertForm,
    convertMediaInfo,
    transcribeForm,
    transcribeMediaInfo,
    submitError,
    submitWarnings,
    parseJsonSafe,
    enforceCategory,
  });

  const chain = useTaskChain({ transcriptionRuntimeConfig });

  const { enableLowData, prepareUploadFiles } = useTranscribeLowDataMode({
    transcribeForm,
    submitError,
  });

  const { submitTask } = useWorkbenchSubmission({
    activeCategory,
    loading,
    submitError,
    submitWarnings,
    enhanceForm,
    convertForm,
    transcribeForm,
    taskIds,
    setStatusQuery,
    fetchStatus,
    joinRoom,
    parseJsonSafe,
    enforceCategory,
    prepareTranscribeUploadFiles: prepareUploadFiles,
    chain,
  });

  const { fetchRecommendations } = useWorkbenchRecommendations({ enhanceForm });

  const syncTranscriptionModel = () => {
    const installed = transcriptionRuntimeConfig.value?.transcription?.installed_models;
    const models = Array.isArray(installed)
      ? installed.map((item) => String(item || "").trim().toLowerCase()).filter((item) => item.length > 0)
      : [];
    if (!models.length) return;

    const current = String(transcribeForm.whisperModel || "").trim().toLowerCase();
    if (models.includes(current)) {
      transcribeForm.whisperModel = current;
      return;
    }

    const active = String(transcriptionRuntimeConfig.value?.transcription?.active_model || "").trim().toLowerCase();
    transcribeForm.whisperModel = models.includes(active) ? active : models[0];
  };

  const fetchTranscriptionRuntimeConfig = async () => {
    try {
      const res = await fetch("/api/transcriptions/runtime-config");
      const data = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(data.error || "读取转录运行配置失败");
      }
      transcriptionRuntimeConfig.value = data;
      if (
        transcribeForm.transcriptionBackend === "elevenlabs"
        && !data?.transcription?.elevenlabs_configured
      ) {
        transcribeForm.transcriptionBackend = "whisper";
      }
      syncTranscriptionModel();
    } catch (error) {
      console.warn(error);
    }
  };

  onMounted(() => {
    initTheme();
    initCategoryRouting();
    fetchRecommendations();
    fetchTranscriptionRuntimeConfig();
    if (!convertForm.watermarkTimeline.length) {
      addWatermarkSegment();
    }
    if (!chain.chainSteps.length) {
      chain.addStep("enhance");
    }
    fetchConstraints();
    initRealtime();
  });

  onUnmounted(() => {
    disposeTheme();
    disposeCategoryRouting();
    disposeRealtime();
  });

  return {
    activeCategory,
    themeMode,
    activeTheme,
    enhanceForm,
    convertForm,
    convertMediaInfo,
    transcribeForm,
    transcribeMediaInfo,
    taskIds,
    submitError,
    submitWarnings,
    statusQuery,
    status,
    statusError,
    loading,
    preview,
    live,
    isPreviewSupported,
    resolution,
    paramRows,
    statusClass,
    progressDetails,
    onEnhanceFileChange,
    onConvertMediaChange,
    onTranscribeMediaChange,
    onTranscribeLowDataToggle: enableLowData,
    onWatermarkImagesChange,
    addWatermarkSegment,
    removeWatermarkSegment,
    transcriptionRuntimeConfig,
    chain,
    submitTask,
    fetchStatus,
    downloadResult,
    onThemeModeChange,
    switchCategory,
    setStatusQuery,
    constraints,
    constraintsStatus,
    getFieldPolicy,
  };
};
