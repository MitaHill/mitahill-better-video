const toTimelinePayload = (timeline) =>
  timeline.map((seg) => ({
    label: seg.label,
    enabled: seg.enabled,
    source_type: seg.sourceType,
    text: seg.text,
    image_index: seg.imageIndex,
    start_sec: seg.startSec,
    end_sec: seg.endSec,
    position: seg.position,
    x_expr: seg.xExpr,
    y_expr: seg.yExpr,
    rotation_deg: seg.rotationDeg,
    alpha: seg.alpha,
    animation: seg.animation,
  }));

export const buildConvertTaskFormData = (convertForm) => {
  const data = new FormData();
  convertForm.mediaFiles.forEach((file) => data.append("media_files", file));
  convertForm.watermarkImages.forEach((file) => data.append("watermark_images", file));

  data.append("convert_mode", convertForm.convertMode);
  data.append("output_format", convertForm.outputFormat);
  data.append("video_codec", convertForm.videoCodec);
  data.append("frame_rate", String(convertForm.frameRate));
  data.append("audio_source_mode", convertForm.audioSourceMode);
  data.append("audio_channels_mode", convertForm.audioChannelsMode);
  data.append("haas_enabled", String(convertForm.haasEnabled));
  data.append("haas_delay_ms", String(convertForm.haasDelayMs));
  data.append("haas_lead", convertForm.haasLead);
  data.append("aspect_ratio", convertForm.aspectRatio);
  data.append("second_pass_reencode", String(convertForm.secondPassReencode));
  data.append("deinterlace", String(convertForm.deinterlace));
  data.append("flip_horizontal", String(convertForm.flipHorizontal));
  data.append("flip_vertical", String(convertForm.flipVertical));
  data.append("video_fade_in_sec", String(convertForm.videoFadeInSec));
  data.append("video_fade_out_sec", String(convertForm.videoFadeOutSec));
  data.append("crf", String(convertForm.crf));
  data.append("video_bitrate_k", String(convertForm.videoBitrateK));
  data.append("target_size_mb", String(convertForm.targetSizeMb));
  data.append("target_width", String(convertForm.targetWidth));
  data.append("target_height", String(convertForm.targetHeight));
  data.append("audio_sample_rate", String(convertForm.audioSampleRate));
  data.append("audio_bitrate_k", String(convertForm.audioBitrateK));
  data.append("mute_audio", String(convertForm.muteAudio));
  data.append("audio_fade_in_sec", String(convertForm.audioFadeInSec));
  data.append("audio_fade_out_sec", String(convertForm.audioFadeOutSec));
  data.append("audio_echo", String(convertForm.audioEcho));
  data.append("audio_echo_delay_ms", String(convertForm.audioEchoDelayMs));
  data.append("audio_echo_decay", String(convertForm.audioEchoDecay));
  data.append("audio_denoise", String(convertForm.audioDenoise));
  data.append("audio_reverse", String(convertForm.audioReverse));
  data.append("audio_volume", String(convertForm.audioVolume));
  data.append("meta_title", convertForm.metaTitle || "");
  data.append("meta_author", convertForm.metaAuthor || "");
  data.append("meta_comment", convertForm.metaComment || "");
  data.append("watermark_enable_text", String(convertForm.watermarkEnableText));
  data.append("watermark_enable_image", String(convertForm.watermarkEnableImage));
  data.append("watermark_default_text", convertForm.watermarkDefaultText || "");
  data.append("watermark_alpha", String(convertForm.watermarkAlpha));
  data.append("watermark_timeline", JSON.stringify(toTimelinePayload(convertForm.watermarkTimeline)));
  data.append("watermark_lua_script", convertForm.watermarkLuaEnabled ? convertForm.watermarkLuaScript || "" : "");
  data.append("frame_export_fps", String(convertForm.frameExportFps));
  data.append("frame_export_fps_mode", String(convertForm.frameExportFpsMode || "manual"));
  data.append("frame_export_format", String(convertForm.frameExportFormat || "jpg"));
  return data;
};
