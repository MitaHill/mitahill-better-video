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
});

export const useWorkbenchFormsState = () => {
  const enhanceForm = reactive({
    inputType: "Video",
    modelName: "realesrgan-x4plus",
    upscale: 3,
    tile: 256,
    recommendationText: "",
    denoise: 0.5,
    crf: 18,
    outputCodec: "",
    outputCodecOptions: [],
    files: [],
  });

  const convertForm = reactive({
    convertMode: "transcode",
    outputFormat: "mp4",
    videoCodec: "h264",
    frameRate: 0,
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
    metaTitle: "",
    metaAuthor: "",
    metaComment: "",
    watermarkEnableText: false,
    watermarkEnableImage: false,
    watermarkDefaultText: "",
    watermarkAlpha: 0.45,
    watermarkImages: [],
    watermarkTimeline: [],
    frameExportFps: 0,
    frameExportFpsMode: "manual",
    frameExportFormat: "jpg",
    mediaFiles: [],
  });

  const convertMediaInfo = ref([]);
  const transcribeForm = reactive({
    transcriptionBackend: "whisper",
    transcribeMode: "subtitle_zip",
    subtitleFormat: "srt",
    whisperModel: "",
    language: "auto",
    translateTo: "",
    translatorProvider: "none",
    maxLineChars: 42,
    temperature: 0,
    beamSize: 5,
    bestOf: 5,
    mediaFiles: [],
    mediaInfo: [],
    lowDataTransfer: false,
    lowDataMessage: "",
  });
  const transcribeMediaInfo = ref([]);

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
    addWatermarkSegment,
    removeWatermarkSegment,
  };
};
