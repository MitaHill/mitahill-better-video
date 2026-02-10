import { formatBool } from "./utils";

export const buildParamRows = (status) => {
  const params = status?.task_params || {};
  if (params.task_category === "convert") {
    return [
      { label: "任务类别", value: "视频转换" },
      { label: "转换类型", value: params.convert_mode || "-" },
      { label: "输出格式", value: (params.output_format || "-").toUpperCase() },
      { label: "视频编码", value: (params.video_codec || "-").toUpperCase() },
      { label: "帧率", value: params.frame_rate || "保持原始" },
      { label: "音频来源", value: params.audio_source_mode || "-" },
      { label: "声道", value: params.audio_channels_mode || "-" },
      { label: "关闭声音", value: formatBool(params.mute_audio) },
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
    return [
      { label: "任务类别", value: "视频转录" },
      { label: "转录类型", value: params.transcribe_mode || "-" },
      { label: "字幕格式", value: (params.subtitle_format || "-").toUpperCase() },
      { label: "Whisper 模型", value: params.whisper_model || "-" },
      { label: "语言", value: params.language || "auto" },
      { label: "温度", value: params.temperature ?? "-" },
      { label: "Beam Size", value: params.beam_size ?? "-" },
      { label: "Best Of", value: params.best_of ?? "-" },
      { label: "时间戳文本", value: formatBool(params.prepend_timestamps) },
      { label: "最大行宽", value: params.max_line_chars ?? "-" },
      { label: "视频输出编码", value: (params.output_video_codec || "-").toUpperCase() },
      { label: "音频码率", value: params.output_audio_bitrate_k ? `${params.output_audio_bitrate_k}k` : "-" },
    ];
  }

  return [
    { label: "任务类别", value: "视频增强" },
    { label: "输入类型", value: params.input_type || "-" },
    { label: "模型", value: params.model_name || "-" },
    { label: "放大倍率", value: params.upscale ? `${params.upscale}x` : "-" },
    { label: "切片大小", value: params.tile ?? "-" },
    { label: "降噪强度", value: params.denoise_strength ?? "-" },
    { label: "保留原音轨", value: params.keep_audio !== undefined ? formatBool(params.keep_audio) : "-" },
    { label: "音频增强", value: params.audio_enhance !== undefined ? formatBool(params.audio_enhance) : "-" },
    { label: "前置降噪", value: params.pre_denoise_mode || "-" },
    { label: "反交错", value: params.deinterlace !== undefined ? formatBool(params.deinterlace) : "-" },
    { label: "输出编码", value: params.output_codec ? params.output_codec.toUpperCase() : "-" },
    { label: "CRF 质量", value: params.crf ?? "-" },
  ];
};

export const buildProgressDetails = (status, live) => {
  if (!status) return "";

  const fallbackProgress = status.task_progress || {};
  const fallbackSegment = status.segment_progress || {};
  const totalFrames = live.totalFrames || fallbackProgress.total_frames || 0;
  const segmentCount = live.segmentCount || fallbackProgress.total_segments || 0;
  const segmentIndex = live.segmentIndex || fallbackSegment.segment_index || 0;
  const segmentTotal = live.segmentTotal || fallbackSegment.total_frames || 0;
  const segmentFrame = live.segmentFrame || fallbackSegment.last_done_frame || 0;
  const totalFrame = live.totalFrame || 0;

  const parts = [];
  if (live.gpu !== null) parts.push(`GPU ${live.gpu}%`);
  if (totalFrames) parts.push(`总帧 ${totalFrame}/${totalFrames}`);
  if (segmentCount) parts.push(`第${segmentIndex}/${segmentCount}段`);
  if (segmentTotal) parts.push(`分段 ${segmentFrame}/${segmentTotal}`);
  return parts.join(" | ");
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
