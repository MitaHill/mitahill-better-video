import { onMounted, onUnmounted, reactive, ref } from "vue";
import { useWorkbenchCategory } from "./workbench/useWorkbenchCategory";
import { useWorkbenchFormsState } from "./workbench/useWorkbenchFormsState";
import { useWorkbenchRecommendations } from "./workbench/useWorkbenchRecommendations";
import { useWorkbenchFormConstraints } from "./workbench/useWorkbenchFormConstraints";
import { useWorkbenchStatus } from "./workbench/useWorkbenchStatus";
import { useWorkbenchSubmission } from "./workbench/useWorkbenchSubmission";
import { useWorkbenchTheme } from "./workbench/useWorkbenchTheme";
import { useWorkbenchUploads } from "./workbench/useWorkbenchUploads";
import { parseJsonSafe } from "./workbench/utils";

export const useWorkbenchController = () => {
  const loading = reactive({ submit: false });
  const submitError = ref("");
  const submitWarnings = ref("");

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

  const { onEnhanceFileChange, onConvertMediaChange, onTranscribeMediaChange, onWatermarkImagesChange, onWatermarkLuaFileChange } = useWorkbenchUploads({
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
  });

  const { fetchRecommendations } = useWorkbenchRecommendations({ enhanceForm });

  onMounted(() => {
    initTheme();
    initCategoryRouting();
    fetchRecommendations();
    if (!convertForm.watermarkTimeline.length) {
      addWatermarkSegment();
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
    isPreviewSupported,
    resolution,
    paramRows,
    statusClass,
    progressDetails,
    onEnhanceFileChange,
    onConvertMediaChange,
    onTranscribeMediaChange,
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
    constraints,
    constraintsStatus,
    getFieldPolicy,
  };
};
