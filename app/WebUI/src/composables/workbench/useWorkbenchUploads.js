import { validateFiles, isFilenameSafe } from "./utils";

const probeMedia = async (file, parseJsonSafe) => {
  const data = new FormData();
  data.append("file", file);
  const res = await fetch("/api/media/probe", { method: "POST", body: data });
  if (!res.ok) {
    const err = await parseJsonSafe(res);
    throw new Error(err.error || `探测失败: ${file.name}`);
  }
  return parseJsonSafe(res);
};

const applyConversionDefaultsByProbe = (convertForm, info) => {
  if (!info) return;

  const hasVideo = info.has_video === true || Number(info.width) > 0 || Number(info.height) > 0 || Number(info.fps) > 0;
  const hasAudio = info.has_audio === true || Number(info.audio_sample_rate) > 0 || Number(info.audio_bitrate) > 0 || Number(info.audio_channels) > 0;

  if (hasVideo && info.fps && Number(info.fps) > 0) {
    convertForm.frameRate = Math.round(Number(info.fps));
    convertForm.frameExportFps = Math.round(Number(info.fps));
  }
  if (hasVideo && info.video_bitrate && Number(info.video_bitrate) > 0) {
    convertForm.videoBitrateK = Math.max(1, Math.round(Number(info.video_bitrate) / 1000));
  }
  if (hasVideo && info.width && Number(info.width) > 0) {
    convertForm.targetWidth = Number(info.width);
  }
  if (hasVideo && info.height && Number(info.height) > 0) {
    convertForm.targetHeight = Number(info.height);
  }
  if (hasVideo) {
    const codec = String(info.video_codec || "").toLowerCase();
    if (codec.includes("265") || codec === "hevc") {
      convertForm.videoCodec = "h265";
    } else if (codec) {
      convertForm.videoCodec = "h264";
    }
  }
  if (hasAudio && info.audio_sample_rate && Number(info.audio_sample_rate) > 0) {
    convertForm.audioSampleRate = Number(info.audio_sample_rate);
  }
  if (hasAudio && info.audio_bitrate && Number(info.audio_bitrate) > 0) {
    convertForm.audioBitrateK = Math.max(32, Math.round(Number(info.audio_bitrate) / 1000));
  }
  if (hasAudio && info.audio_channels === 1) {
    convertForm.audioChannelsMode = "mono";
  } else if (hasAudio && info.audio_channels >= 2) {
    convertForm.audioChannelsMode = "stereo";
  }
};

export const useWorkbenchUploads = ({
  enhanceForm,
  convertForm,
  convertMediaInfo,
  transcribeForm,
  transcribeMediaInfo,
  submitError,
  submitWarnings,
  parseJsonSafe,
  enforceCategory,
}) => {
  const onEnhanceFileChange = (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length && !validateFiles(files)) {
      submitError.value = "文件名包含非法字符或过长，请重命名后上传。";
      enhanceForm.files = [];
      event.target.value = "";
      return;
    }
    enhanceForm.files = files;
    if (typeof enforceCategory === "function") {
      enforceCategory("enhance");
    }
  };

  const onConvertMediaChange = async (event) => {
    submitError.value = "";
    submitWarnings.value = "";
    const files = Array.from(event.target.files || []);
    if (files.length && !validateFiles(files)) {
      submitError.value = "媒体文件名包含非法字符或过长。";
      convertForm.mediaFiles = [];
      convertMediaInfo.value = [];
      event.target.value = "";
      return;
    }

    convertForm.mediaFiles = files;
    convertMediaInfo.value = [];
    const probeErrors = [];

    for (const file of files) {
      try {
        const info = await probeMedia(file, parseJsonSafe);
        convertMediaInfo.value.push(info);
        applyConversionDefaultsByProbe(convertForm, info);
      } catch (error) {
        probeErrors.push(`${file.name}: ${error.message}`);
      }
    }

    if (probeErrors.length) {
      submitWarnings.value = `以下文件参数探测失败：${probeErrors.join("；")}`;
    }
    if (typeof enforceCategory === "function") {
      enforceCategory("convert");
    }
    event.target.value = "";
  };

  const onWatermarkImagesChange = (event) => {
    const files = Array.from(event.target.files || []);
    if (files.length && !validateFiles(files)) {
      submitError.value = "水印图片文件名包含非法字符或过长。";
      convertForm.watermarkImages = [];
      event.target.value = "";
      return;
    }
    convertForm.watermarkImages = files;
    if (typeof enforceCategory === "function") {
      enforceCategory("convert");
    }
  };

  const onWatermarkLuaFileChange = async (event) => {
    const file = (event.target.files || [])[0];
    if (!file) return;
    if (!isFilenameSafe(file.name)) {
      submitError.value = "Lua 脚本文件名包含非法字符或过长。";
      event.target.value = "";
      return;
    }
    try {
      convertForm.watermarkLuaScript = await file.text();
    } catch (_err) {
      submitError.value = "读取 Lua 脚本文件失败。";
    } finally {
      if (typeof enforceCategory === "function") {
        enforceCategory("convert");
      }
      event.target.value = "";
    }
  };

  const onTranscribeMediaChange = async (event) => {
    submitError.value = "";
    submitWarnings.value = "";
    const files = Array.from(event.target.files || []);
    if (files.length && !validateFiles(files)) {
      submitError.value = "转录媒体文件名包含非法字符或过长。";
      transcribeForm.mediaFiles = [];
      transcribeMediaInfo.value = [];
      event.target.value = "";
      return;
    }

    transcribeForm.mediaFiles = files;
    transcribeMediaInfo.value = [];
    const probeErrors = [];
    for (const file of files) {
      try {
        const info = await probeMedia(file, parseJsonSafe);
        transcribeMediaInfo.value.push(info);
      } catch (error) {
        probeErrors.push(`${file.name}: ${error.message}`);
      }
    }
    if (probeErrors.length) {
      submitWarnings.value = `以下转录文件探测失败：${probeErrors.join("；")}`;
    }
    if (typeof enforceCategory === "function") {
      enforceCategory("transcribe");
    }
    event.target.value = "";
  };

  return {
    onEnhanceFileChange,
    onConvertMediaChange,
    onTranscribeMediaChange,
    onWatermarkImagesChange,
    onWatermarkLuaFileChange,
  };
};
