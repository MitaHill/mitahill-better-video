export const useWorkbenchRecommendations = ({ enhanceForm }) => {
  const fetchRecommendations = async () => {
    try {
      const res = await fetch("/api/config/recommendations");
      if (!res.ok) return;
      const payload = await res.json();
      if (payload?.tile_size) {
        enhanceForm.tile = Number(payload.tile_size);
      }
      if (payload?.upscale) {
        enhanceForm.upscale = Number(payload.upscale);
      }
      if (Array.isArray(payload?.enhance_output_codecs) && payload.enhance_output_codecs.length) {
        enhanceForm.outputCodecOptions = payload.enhance_output_codecs;
        if (!enhanceForm.outputCodecOptions.includes(enhanceForm.outputCodec)) {
          enhanceForm.outputCodec = enhanceForm.outputCodecOptions[0];
        }
      }
    } catch (_err) {
      // ignore recommendation failures
    }
  };

  return {
    fetchRecommendations,
  };
};
