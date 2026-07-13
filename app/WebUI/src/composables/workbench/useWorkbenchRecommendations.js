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
      if (payload?.gpu_name || payload?.vram_gb) {
        const gpu = payload.gpu_name || "当前 GPU";
        const vram = payload.vram_gb ? `${Number(payload.vram_gb).toFixed(1)}GB` : "未知显存";
        enhanceForm.recommendationText = `已按 ${gpu} / ${vram} 自动推荐：${enhanceForm.tile} tile，${enhanceForm.upscale}x`;
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
