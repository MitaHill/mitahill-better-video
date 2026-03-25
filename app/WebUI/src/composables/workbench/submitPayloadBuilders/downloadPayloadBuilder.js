export const buildDownloadTaskFormData = (downloadForm) => {
  const data = new FormData();
  data.append("source_url", String(downloadForm.sourceUrl || "").trim());
  data.append("source_title", String(downloadForm.sourceTitle || "").trim());
  data.append("source_duration_sec", String(Number(downloadForm.sourceDurationSec || 0)));
  data.append("source_width", String(Number(downloadForm.sourceWidth || 0)));
  data.append("source_height", String(Number(downloadForm.sourceHeight || 0)));
  data.append("source_fps", String(Number(downloadForm.sourceFps || 0)));
  data.append("source_size_mb", String(Number(downloadForm.sourceSizeMb || 0)));
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
