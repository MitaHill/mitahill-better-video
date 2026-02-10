import { onMounted, onUnmounted, reactive, ref } from "vue";
import { useWorkbenchCategory } from "./workbench/useWorkbenchCategory";
import { useWorkbenchFormsState } from "./workbench/useWorkbenchFormsState";
import { useWorkbenchRecommendations } from "./workbench/useWorkbenchRecommendations";
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

  const { enhanceForm, convertForm, convertMediaInfo, addWatermarkSegment, removeWatermarkSegment } = useWorkbenchFormsState();

  const {
    taskIds,
    statusQuery,
    status,
    statusError,
    preview,
    isConversionTask,
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

  const { onEnhanceFileChange, onConvertMediaChange, onWatermarkImagesChange, onWatermarkLuaFileChange } = useWorkbenchUploads({
    enhanceForm,
    convertForm,
    convertMediaInfo,
    submitError,
    submitWarnings,
    parseJsonSafe,
  });

  const { submitTask } = useWorkbenchSubmission({
    activeCategory,
    loading,
    submitError,
    submitWarnings,
    enhanceForm,
    convertForm,
    taskIds,
    setStatusQuery,
    fetchStatus,
    joinRoom,
    parseJsonSafe,
  });

  const { fetchRecommendations } = useWorkbenchRecommendations({ enhanceForm });

  onMounted(() => {
    initTheme();
    initCategoryRouting();
    fetchRecommendations();
    if (!convertForm.watermarkTimeline.length) {
      addWatermarkSegment();
    }
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
  };
};
