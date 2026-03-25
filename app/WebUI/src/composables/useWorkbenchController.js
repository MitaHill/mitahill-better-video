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
    live,
    liveNowMs,
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
    downloadForm,
    taskIds,
    setStatusQuery,
    fetchStatus,
    joinRoom,
    parseJsonSafe,
    enforceCategory,
  });

  const { fetchRecommendations } = useWorkbenchRecommendations({ enhanceForm });

  const syncDownloadSourceMetrics = (probeData = null) => {
    const fallbackWidth = Number(downloadForm.probeWidth || probeData?.width || 0);
    const fallbackHeight = Number(downloadForm.probeHeight || probeData?.height || 0);
    const fallbackFps = Number(downloadForm.probeFps || probeData?.fps || 0);
    const fallbackSizeMb = Number(downloadForm.probeSizeMb || probeData?.size_mb || 0);

    if (downloadForm.downloadMode !== "video") {
      // 只有视频模式才需要跟随清晰度选项切换分辨率。
      // 音频/字幕模式保持 probe 的原始元数据即可，状态页仍然能显示来源信息。
      downloadForm.sourceWidth = fallbackWidth;
      downloadForm.sourceHeight = fallbackHeight;
      downloadForm.sourceFps = fallbackFps;
      downloadForm.sourceSizeMb = fallbackSizeMb;
      return;
    }

    const selected = Array.isArray(downloadForm.qualityOptions)
      ? downloadForm.qualityOptions.find((item) => item.value === downloadForm.qualitySelector)
      : null;

    // 视频模式下，任务状态面板展示的是“当前选中清晰度”的信息，
    // 而不是 probe 出来的一个笼统最高值。这样用户改档位后右侧数据会同步变化。
    downloadForm.sourceWidth = Number(selected?.width || fallbackWidth || 0);
    downloadForm.sourceHeight = Number(selected?.height || fallbackHeight || 0);
    downloadForm.sourceFps = Number(selected?.fps || fallbackFps || 0);
    downloadForm.sourceSizeMb = Number(selected?.size_mb || fallbackSizeMb || 0);
  };

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
      downloadForm.probeWidth = Number(data.width || 0);
      downloadForm.probeHeight = Number(data.height || 0);
      downloadForm.probeFps = Number(data.fps || 0);
      downloadForm.probeSizeMb = Number(data.size_mb || 0);
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
      syncDownloadSourceMetrics(data);
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
    downloadForm,
    taskIds,
    submitError,
    submitWarnings,
    statusQuery,
    status,
    statusError,
    loading,
    preview,
    live,
    liveNowMs,
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
  };
};
