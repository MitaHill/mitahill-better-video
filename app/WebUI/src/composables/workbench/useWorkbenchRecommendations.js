export const useWorkbenchRecommendations = ({ enhanceForm }) => {
  const fetchRecommendations = async () => {
    try {
      const res = await fetch("/api/config/recommendations");
      if (!res.ok) return;
      const payload = await res.json();
      if (payload?.tile_size) {
        enhanceForm.tile = Number(payload.tile_size);
      }
      if (typeof payload?.audio_enhancement_default === "boolean") {
        enhanceForm.audioEnhance = payload.audio_enhancement_default;
      }
      if (payload?.pre_denoise_default) {
        enhanceForm.preDenoiseMode = payload.pre_denoise_default;
      }
    } catch (_err) {
      // ignore recommendation failures
    }
  };

  return {
    fetchRecommendations,
  };
};
