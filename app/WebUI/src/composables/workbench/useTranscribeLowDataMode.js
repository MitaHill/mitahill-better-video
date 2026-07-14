const MIN_CHROME_VERSION = 109;

const chromeVersion = () => {
  const brands = navigator.userAgentData?.brands || [];
  const chromium = brands.find((item) => /Chromium|Google Chrome/i.test(item.brand || ""));
  if (chromium?.version) {
    return Number.parseInt(chromium.version, 10);
  }

  const matched = navigator.userAgent.match(/(?:Chrome|Chromium)\/(\d+)/i);
  return matched ? Number.parseInt(matched[1], 10) : 0;
};

const assertBrowserSupport = () => {
  const version = chromeVersion();
  if (!version || version < MIN_CHROME_VERSION) {
    throw new Error(`低数据传输需要 Chrome ${MIN_CHROME_VERSION}+。`);
  }
  if (!window.WebAssembly || !window.Worker || !window.Blob || !window.File) {
    throw new Error("当前浏览器缺少低数据传输所需能力。");
  }
};

const basename = (name) => {
  const safe = String(name || "media").replace(/\.[^.]+$/, "");
  return safe.replace(/[^\w.-]+/g, "_").slice(0, 80) || "media";
};

const extension = (name) => {
  const matched = String(name || "").match(/\.([a-z0-9]{1,8})$/i);
  return matched ? `.${matched[1].toLowerCase()}` : "";
};

export const useTranscribeLowDataMode = ({ transcribeForm, submitError }) => {
  let ffmpeg = null;
  let loading = null;

  const setMessage = (message) => {
    transcribeForm.lowDataMessage = message;
  };

  const loadFfmpeg = async () => {
    assertBrowserSupport();
    if (ffmpeg?.loaded) return ffmpeg;
    if (loading) return loading;

    setMessage("正在加载 ffmpeg.wasm...");
    loading = (async () => {
      const { FFmpeg } = await import("@ffmpeg/ffmpeg");
      const instance = new FFmpeg();
      await instance.load({
        coreURL: "/ffmpeg/ffmpeg-core.js",
        wasmURL: "/ffmpeg/ffmpeg-core.wasm",
      });
      ffmpeg = instance;
      setMessage("低数据传输已就绪。");
      return instance;
    })();

    try {
      return await loading;
    } finally {
      loading = null;
    }
  };

  const enableLowData = async () => {
    if (!transcribeForm.lowDataTransfer) {
      setMessage("");
      return;
    }

    transcribeForm.transcribeMode = "subtitle_zip";
    try {
      await loadFfmpeg();
      if (!transcribeForm.lowDataTransfer) {
        setMessage("");
      }
    } catch (error) {
      transcribeForm.lowDataTransfer = false;
      setMessage(error.message);
      submitError.value = error.message;
    }
  };

  const extractAudio = async (file, index) => {
    const instance = await loadFfmpeg();
    const inputName = `input_${index}${extension(file.name)}`;
    const outputName = `output_${index}.m4a`;
    const data = new Uint8Array(await file.arrayBuffer());

    setMessage(`正在提取音频：${file.name}`);
    await instance.writeFile(inputName, data);
    try {
      await instance.exec([
        "-i",
        inputName,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        outputName,
      ]);
      const output = await instance.readFile(outputName);
      const bytes = output instanceof Uint8Array ? output : new Uint8Array(output);
      return new File([bytes], `${basename(file.name)}.m4a`, { type: "audio/mp4" });
    } finally {
      await instance.deleteFile(inputName).catch(() => {});
      await instance.deleteFile(outputName).catch(() => {});
    }
  };

  const prepareUploadFiles = async () => {
    if (!transcribeForm.lowDataTransfer) return transcribeForm.mediaFiles;
    transcribeForm.transcribeMode = "subtitle_zip";

    const files = Array.isArray(transcribeForm.mediaFiles) ? transcribeForm.mediaFiles : [];
    const mediaInfo = Array.isArray(transcribeForm.mediaInfo) ? transcribeForm.mediaInfo : [];
    const prepared = [];
    for (let idx = 0; idx < files.length; idx += 1) {
      const file = files[idx];
      const info = mediaInfo[idx] || {};
      const isAudioOnly =
        (info.has_audio === true && info.has_video !== true) || String(file.type || "").startsWith("audio/");
      if (!isAudioOnly) {
        prepared.push(await extractAudio(file, idx));
      } else {
        prepared.push(file);
      }
    }
    setMessage("音频提取完成，正在提交任务。");
    return prepared;
  };

  return {
    enableLowData,
    prepareUploadFiles,
  };
};
