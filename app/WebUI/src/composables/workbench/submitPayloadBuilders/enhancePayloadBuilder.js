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
  data.append("crf", String(enhanceForm.crf));
  data.append("output_codec", String(enhanceForm.outputCodec));
  return data;
};
