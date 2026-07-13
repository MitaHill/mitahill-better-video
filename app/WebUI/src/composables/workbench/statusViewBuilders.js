import { formatBool } from "./utils";

const STAGE_LABELS = {
  enhance: "增强处理中",
  prepare: "准备中",
  encode: "编码中",
  audio: "音频处理中",
  finalize: "后处理",
  transcribe: "语音识别中",
  write_subtitle: "写入字幕",
  translate: "翻译中",
  render_video: "封装字幕视频",
  download: "下载中",
  package: "封装处理中",
  completed: "已完成",
};

export const resolveStageLabel = (stage, category = "") => {
  const safeStage = String(stage || "").trim().toLowerCase();
  if (safeStage && STAGE_LABELS[safeStage]) {
    return STAGE_LABELS[safeStage];
  }
  // stage 为空时，根据任务类别兜底一个大类标签。
  // 这样旧任务或非实时事件来源仍然能显示一条可读状态，而不是直接空白。
  const safeCategory = String(category || "").trim().toLowerCase();
  if (safeCategory === "enhance") return "增强处理中";
  if (safeCategory === "convert") return "处理中";
  if (safeCategory === "transcribe") return "转录处理中";
  if (safeCategory === "download") return "下载处理中";
  return "";
};

export const buildParamRows = (status) => {
  const params = status?.task_params || {};
  // 这里刻意做成“每类任务一张独立表”，而不是把所有字段平铺到一个超长列表。
  // 状态页的目标是快速回忆任务配置，不是复刻提交表单。
  if (params.task_category === "convert") {
    return [
      { label: "任务类别", value: "视频转换" },
      { label: "转换类型", value: params.convert_mode || "-" },
      { label: "输出格式", value: (params.output_format || "-").toUpperCase() },
      { label: "视频编码", value: (params.video_codec || "-").toUpperCase() },
      { label: "帧率", value: params.frame_rate || "保持原始" },
      { label: "反交错", value: formatBool(params.deinterlace) },
      { label: "左右颠倒", value: formatBool(params.flip_horizontal) },
      { label: "上下颠倒", value: formatBool(params.flip_vertical) },
      { label: "二次编码", value: formatBool(params.second_pass_reencode) },
      { label: "水印文字", value: formatBool(params.watermark_enable_text) },
      { label: "水印图片", value: formatBool(params.watermark_enable_image) },
      { label: "标题", value: params.meta_title || "-" },
      { label: "作者", value: params.meta_author || "-" },
    ];
  }
  if (params.task_category === "transcribe") {
    const modeLabelMap = {
      subtitle_zip: "字幕与文本（单文件直出 / 批量 ZIP）",
      subtitled_video: "带字幕视频（单视频直出 / 批量 ZIP）",
      subtitle_and_video_zip: "字幕与视频（统一 ZIP）",
    };
    const providerLabelMap = {
      none: "不启用",
      openai_compatible: "OpenAI 兼容",
    };
    return [
      { label: "任务类别", value: "视频转录" },
      { label: "转录类型", value: modeLabelMap[params.transcribe_mode] || params.transcribe_mode || "-" },
      { label: "字幕格式", value: (params.subtitle_format || "-").toUpperCase() },
      { label: "Whisper 模型", value: params.whisper_model || "-" },
      { label: "语言", value: params.language || "auto" },
      { label: "翻译到", value: params.translate_to || "-" },
      { label: "翻译提供器", value: providerLabelMap[params.translator_provider] || params.translator_provider || "-" },
      { label: "温度", value: params.temperature ?? "-" },
      { label: "Beam Size", value: params.beam_size ?? "-" },
      { label: "Best Of", value: params.best_of ?? "-" },
      { label: "最大行宽", value: params.max_line_chars ?? "-" },
    ];
  }
  if (params.task_category === "download") {
    const modeLabel = {
      video: "视频",
      audio: "仅音频",
      subtitle_only: "仅字幕",
    };
    return [
      { label: "任务类别", value: "视频下载" },
      { label: "下载类型", value: modeLabel[params.download_mode] || params.download_mode || "-" },
      { label: "源链接", value: params.source_url || "-" },
      { label: "清晰度选择", value: params.quality_selector || "-" },
      { label: "视频封装", value: (params.video_output_format || "-").toUpperCase() },
      { label: "音频格式", value: (params.audio_output_format || "-").toUpperCase() },
      { label: "字幕格式", value: (params.subtitle_output_format || "-").toUpperCase() },
      { label: "字幕语言", value: Array.isArray(params.subtitle_languages) ? params.subtitle_languages.join(", ") || "-" : "-" },
      { label: "包含自动字幕", value: formatBool(params.subtitle_include_auto) },
    ];
  }

  return [
    { label: "任务类别", value: "视频增强" },
    { label: "输入类型", value: params.input_type || "-" },
    { label: "模型", value: params.model_name || "-" },
    { label: "放大倍率", value: params.upscale ? `${params.upscale}x` : "-" },
    { label: "切片大小", value: params.tile ?? "-" },
    { label: "降噪强度", value: params.denoise_strength ?? "-" },
    { label: "输出编码", value: params.output_codec ? params.output_codec.toUpperCase() : "-" },
    { label: "CRF 质量", value: params.crf ?? "-" },
  ];
};

export const buildProgressDetails = () => {
  // 实时状态已经由 StatusProgressSummary 的矩形信息卡展示。
  // 这里保留函数接口，避免改动调用链，但不再生成重复的文字摘要。
  return "";
};

export const resolveStatusClass = (status) => {
  if (!status) return "status-pending";
  const map = {
    PENDING: "status-pending",
    PROCESSING: "status-processing",
    COMPLETED: "status-completed",
    FAILED: "status-failed",
  };
  return map[status.status] || "status-pending";
};
