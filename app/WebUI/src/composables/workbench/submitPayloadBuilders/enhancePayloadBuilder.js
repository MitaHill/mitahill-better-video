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
