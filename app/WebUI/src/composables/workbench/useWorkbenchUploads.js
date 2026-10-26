import { validateFiles } from "./utils.js";

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

  const onTranscribeMediaChange = async (event) => {
    submitError.value = "";
    submitWarnings.value = "";
    const files = Array.from(event.target.files || []);
    if (files.length && !validateFiles(files)) {
      submitError.value = "转录媒体文件名包含非法字符或过长。";
      transcribeForm.mediaFiles = [];
      transcribeForm.mediaInfo = [];
      transcribeMediaInfo.value = [];
      event.target.value = "";
      return;
    }

    transcribeForm.mediaFiles = files;
    transcribeForm.mediaInfo = [];
    transcribeMediaInfo.value = [];
    const probeErrors = [];
    for (const file of files) {
      try {
        const info = await probeMedia(file, parseJsonSafe);
        transcribeMediaInfo.value.push(info);
        transcribeForm.mediaInfo.push(info);
      } catch (error) {
        transcribeForm.mediaInfo.push(null);
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
  };
};
