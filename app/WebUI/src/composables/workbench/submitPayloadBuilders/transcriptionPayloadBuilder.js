export const buildTranscriptionTaskFormData = (transcribeForm) => {
  const data = new FormData();
  transcribeForm.mediaFiles.forEach((file) => data.append("media_files", file));

  data.append("transcribe_mode", transcribeForm.transcribeMode);
  data.append("subtitle_format", transcribeForm.subtitleFormat);
  data.append("whisper_model", transcribeForm.whisperModel);
  data.append("language", transcribeForm.language);
  data.append("translate_to", transcribeForm.translateTo || "");
  data.append("translator_provider", transcribeForm.translateTo ? "openai_compatible" : "none");
  data.append("generate_bilingual", String(transcribeForm.generateBilingual));
  data.append("export_json", String(transcribeForm.exportJson));
  data.append("prepend_timestamps", String(transcribeForm.prependTimestamps));
  data.append("max_line_chars", String(transcribeForm.maxLineChars));
  data.append("temperature", String(transcribeForm.temperature));
  data.append("beam_size", String(transcribeForm.beamSize));
  data.append("best_of", String(transcribeForm.bestOf));
  return data;
};
