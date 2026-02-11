import { reactive, ref } from "vue";

const buildSegment = (label = "A") => ({
  id: `${Date.now()}_${Math.random()}`,
  label,
  enabled: true,
  sourceType: "text",
  text: "",
  imageIndex: 0,
  startSec: 0,
  endSec: 3,
  position: "bottom_right",
  xExpr: "W-w-24",
  yExpr: "H-h-24",
  rotationDeg: 0,
  alpha: 0.45,
  animation: "none",
});

export const useWorkbenchFormsState = () => {
  const enhanceForm = reactive({
    inputType: "Video",
    modelName: "realesrgan-x4plus",
    upscale: 3,
    tile: 256,
    denoise: 0.5,
    keepAudio: true,
    audioEnhance: false,
    preDenoiseMode: "off",
    haasEnabled: false,
    haasDelayMs: 0,
    haasLead: "left",
    crf: 18,
    outputCodec: "h264",
    deinterlace: false,
    files: [],
  });

  const convertForm = reactive({
    convertMode: "transcode",
    outputFormat: "mp4",
    videoCodec: "h264",
    frameRate: 0,
    audioSourceMode: "keep_original",
    audioChannelsMode: "keep",
    haasEnabled: false,
    haasDelayMs: 0,
    haasLead: "left",
    aspectRatio: "",
    secondPassReencode: false,
    deinterlace: false,
    flipHorizontal: false,
    flipVertical: false,
    videoFadeInSec: 0,
    videoFadeOutSec: 0,
    crf: 18,
    videoBitrateK: 0,
    targetSizeMb: 0,
    targetWidth: 0,
    targetHeight: 0,
    audioSampleRate: 0,
    audioBitrateK: 192,
    muteAudio: false,
    audioFadeInSec: 0,
    audioFadeOutSec: 0,
    audioEcho: false,
    audioEchoDelayMs: 200,
    audioEchoDecay: 0.4,
    audioDenoise: false,
    audioReverse: false,
    audioVolume: 1,
    metaTitle: "",
    metaAuthor: "",
    metaComment: "",
    watermarkEnableText: false,
    watermarkEnableImage: false,
    watermarkDefaultText: "",
    watermarkAlpha: 0.45,
    watermarkImages: [],
    watermarkTimeline: [],
    watermarkLuaEnabled: false,
    watermarkLuaScript: "",
    frameExportFps: 0,
    frameExportFpsMode: "manual",
    frameExportFormat: "jpg",
    mediaFiles: [],
  });

  const convertMediaInfo = ref([]);
  const transcribeForm = reactive({
    transcribeMode: "subtitle_zip",
    subtitleFormat: "srt",
    whisperModel: "whisper-openai/medium",
    language: "auto",
    translateTo: "zh",
    translatorTimeoutSec: 120,
    generateBilingual: true,
    exportJson: false,
    prependTimestamps: false,
    maxLineChars: 42,
    temperature: 0,
    beamSize: 5,
    bestOf: 5,
    outputVideoCodec: "h264",
    outputAudioBitrateK: 192,
    mediaFiles: [],
  });
  const transcribeMediaInfo = ref([]);
  const downloadForm = reactive({
    sourceUrl: "",
    sourceTitle: "",
    sourceDurationSec: 0,
    downloadMode: "video",
    qualitySelector: "bestvideo*+bestaudio/best",
    qualityOptions: [],
    maxQualityLabel: "",
    videoOutputFormat: "mp4",
    audioOutputFormat: "mp3",
    subtitleOutputFormat: "srt",
    subtitleLanguagesOptions: [],
    subtitleLanguages: [],
    subtitleIncludeAuto: true,
    probeLoading: false,
    probeReady: false,
    probeError: "",
    probeMessage: "",
  });

  const addWatermarkSegment = () => {
    const label = String.fromCharCode(65 + convertForm.watermarkTimeline.length);
    convertForm.watermarkTimeline.push(buildSegment(label));
  };

  const removeWatermarkSegment = (idx) => {
    convertForm.watermarkTimeline.splice(idx, 1);
  };

  return {
    enhanceForm,
    convertForm,
    convertMediaInfo,
    transcribeForm,
    transcribeMediaInfo,
    downloadForm,
    addWatermarkSegment,
    removeWatermarkSegment,
  };
};
