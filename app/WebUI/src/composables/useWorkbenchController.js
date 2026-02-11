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
  const transcribeRuntime = reactive({
    loading: false,
    error: "",
    transcription: {
      backend: "whisper",
      active_model: "medium",
    },
    translation: {
      provider: "none",
      model: "",
      base_url: "",
      enabled: false,
    },
  });

  const { themeMode, activeTheme, onThemeModeChange, initTheme, disposeTheme } = useWorkbenchTheme();
  const { activeCategory, switchCategory, initCategoryRouting, disposeCategoryRouting } = useWorkbenchCategory();

  const {
    enhanceForm,
    convertForm,
    convertMediaInfo,
    transcribeForm,
    transcribeMediaInfo,
    downloadForm,
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
    streamLines,
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
    downloadForm,
    taskIds,
    setStatusQuery,
    fetchStatus,
    joinRoom,
    parseJsonSafe,
    enforceCategory,
  });

  const { fetchRecommendations } = useWorkbenchRecommendations({ enhanceForm });

  const probeDownloadSource = async () => {
    downloadForm.probeError = "";
    downloadForm.probeMessage = "";
    downloadForm.probeLoading = true;
    try {
      const url = String(downloadForm.sourceUrl || "").trim();
      if (!url) {
        throw new Error("请先输入下载链接。");
      }
      const payload = new FormData();
      payload.append("url", url);
      const res = await fetch("/api/downloads/probe", { method: "POST", body: payload });
      const data = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(data.error || "解析失败");
      }
      downloadForm.probeReady = true;
      downloadForm.sourceTitle = String(data.title || "");
      downloadForm.sourceDurationSec = Number(data.duration_sec || 0);
      downloadForm.maxQualityLabel = String(data.max_quality_label || "");
      downloadForm.qualityOptions = Array.isArray(data.quality_options) ? data.quality_options : [];
      const subtitleRows = Array.isArray(data.subtitle_languages) ? data.subtitle_languages : [];
      downloadForm.subtitleLanguagesOptions = [
        { code: "all", label: "all（全部可用语言）", has_manual: true, has_auto: true },
        ...subtitleRows,
      ];
      if (!downloadForm.qualitySelector && downloadForm.qualityOptions.length) {
        downloadForm.qualitySelector = String(downloadForm.qualityOptions[0].value || "bestvideo*+bestaudio/best");
      }
      if (downloadForm.qualityOptions.length && !downloadForm.qualityOptions.some((item) => item.value === downloadForm.qualitySelector)) {
        downloadForm.qualitySelector = String(downloadForm.qualityOptions[0].value || "bestvideo*+bestaudio/best");
      }
      downloadForm.probeMessage = `解析完成：${downloadForm.sourceTitle || "未知标题"}`;
      if (!downloadForm.subtitleLanguages.length && downloadForm.subtitleLanguagesOptions.length) {
        downloadForm.subtitleLanguages = ["all"];
      }
    } catch (error) {
      downloadForm.probeError = error.message;
      downloadForm.probeReady = false;
    } finally {
      downloadForm.probeLoading = false;
    }
  };

  const fetchTranscribeRuntimeConfig = async () => {
    transcribeRuntime.loading = true;
    transcribeRuntime.error = "";
    try {
      const res = await fetch("/api/transcriptions/runtime-config");
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(payload.error || "读取转录运行配置失败");
      }
      transcribeRuntime.transcription = payload.transcription || transcribeRuntime.transcription;
      transcribeRuntime.translation = payload.translation || transcribeRuntime.translation;
    } catch (error) {
      transcribeRuntime.error = error.message;
    } finally {
      transcribeRuntime.loading = false;
    }
  };

  onMounted(() => {
    initTheme();
    initCategoryRouting();
    fetchRecommendations();
    if (!convertForm.watermarkTimeline.length) {
      addWatermarkSegment();
    }
    fetchConstraints();
    fetchTranscribeRuntimeConfig();
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
    streamLines,
    onEnhanceFileChange,
    onConvertMediaChange,
    onTranscribeMediaChange,
    onWatermarkImagesChange,
    onWatermarkLuaFileChange,
    probeDownloadSource,
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
    transcribeRuntime,
  };
};
