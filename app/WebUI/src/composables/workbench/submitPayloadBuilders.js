export const buildEnhanceTaskFormData = (enhanceForm) => {
  const data = new FormData();
  if (enhanceForm.files.length > 1) {
    enhanceForm.files.forEach((file) => data.append("files", file));
  } else {
    data.append("file", enhanceForm.files[0]);
  }

  data.append("input_type", enhanceForm.inputType);
  data.append("model_name", enhanceForm.modelName);
  data.append("upscale", String(enhanceForm.upscale));
  data.append("tile", String(enhanceForm.tile));
  data.append("denoise_strength", String(enhanceForm.denoise));
  data.append("keep_audio", String(enhanceForm.keepAudio));
  data.append("audio_enhance", String(enhanceForm.audioEnhance));
  data.append("pre_denoise_mode", String(enhanceForm.preDenoiseMode));
  data.append("haas_enabled", String(enhanceForm.haasEnabled));
  data.append("haas_delay_ms", String(enhanceForm.haasDelayMs));
  data.append("haas_lead", String(enhanceForm.haasLead));
  data.append("crf", String(enhanceForm.crf));
  data.append("output_codec", String(enhanceForm.outputCodec));
  data.append("deinterlace", String(enhanceForm.deinterlace));
  return data;
};

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
  data.append(
    "watermark_timeline",
    JSON.stringify(
      convertForm.watermarkTimeline.map((seg) => ({
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
      }))
    )
  );
  data.append("watermark_lua_script", convertForm.watermarkLuaEnabled ? convertForm.watermarkLuaScript || "" : "");
  data.append("frame_export_fps", String(convertForm.frameExportFps));
  data.append("frame_export_fps_mode", String(convertForm.frameExportFpsMode || "manual"));
  data.append("frame_export_format", String(convertForm.frameExportFormat || "jpg"));

  return data;
};

export const buildTranscriptionTaskFormData = (transcribeForm) => {
  const data = new FormData();
  transcribeForm.mediaFiles.forEach((file) => data.append("media_files", file));

  data.append("transcribe_mode", transcribeForm.transcribeMode);
  data.append("subtitle_format", transcribeForm.subtitleFormat);
  data.append("whisper_model", transcribeForm.whisperModel);
  data.append("language", transcribeForm.language);
  data.append("translate_to", transcribeForm.translateTo || "");
  data.append("translator_provider", transcribeForm.translatorProvider || "none");
  data.append("translator_base_url", transcribeForm.translatorBaseUrl || "");
  data.append("translator_model", transcribeForm.translatorModel || "");
  data.append("translator_api_key", transcribeForm.translatorApiKey || "");
  data.append("translator_prompt", transcribeForm.translatorPrompt || "");
  data.append("translator_timeout_sec", String(transcribeForm.translatorTimeoutSec || 120));
  data.append("generate_bilingual", String(transcribeForm.generateBilingual));
  data.append("export_json", String(transcribeForm.exportJson));
  data.append("prepend_timestamps", String(transcribeForm.prependTimestamps));
  data.append("max_line_chars", String(transcribeForm.maxLineChars));
  data.append("temperature", String(transcribeForm.temperature));
  data.append("beam_size", String(transcribeForm.beamSize));
  data.append("best_of", String(transcribeForm.bestOf));
  data.append("output_video_codec", transcribeForm.outputVideoCodec);
  data.append("output_audio_bitrate_k", String(transcribeForm.outputAudioBitrateK));

  return data;
};

export const buildDownloadTaskFormData = (downloadForm) => {
  const data = new FormData();
  data.append("source_url", String(downloadForm.sourceUrl || "").trim());
  data.append("source_title", String(downloadForm.sourceTitle || "").trim());
  data.append("source_duration_sec", String(Number(downloadForm.sourceDurationSec || 0)));
  data.append("download_mode", String(downloadForm.downloadMode || "video"));
  data.append("quality_selector", String(downloadForm.qualitySelector || "bestvideo*+bestaudio/best"));
  data.append("video_output_format", String(downloadForm.videoOutputFormat || "mp4"));
  data.append("audio_output_format", String(downloadForm.audioOutputFormat || "mp3"));
  data.append("subtitle_output_format", String(downloadForm.subtitleOutputFormat || "srt"));
  data.append("subtitle_include_auto", String(Boolean(downloadForm.subtitleIncludeAuto)));
  const langs = Array.isArray(downloadForm.subtitleLanguages) ? downloadForm.subtitleLanguages : [];
  if (langs.length) {
    langs.forEach((item) => data.append("subtitle_languages", String(item || "").trim()));
  } else {
    data.append("subtitle_languages", "all");
  }
  return data;
};
