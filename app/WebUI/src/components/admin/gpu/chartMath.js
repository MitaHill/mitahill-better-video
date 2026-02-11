export const GPU_RANGE_OPTIONS = Object.freeze([
  { value: 60, label: "最近 1 分钟" },
  { value: 300, label: "最近 5 分钟" },
  { value: 900, label: "最近 15 分钟" },
  { value: 3600, label: "最近 1 小时" },
]);

const GPU_LINE_COLORS = Object.freeze(["#4f8cff", "#3fd0a4", "#f4a261", "#8a7dff"]);
const VRAM_LINE_COLORS = Object.freeze(["#ff4d4f", "#ff7875", "#ff9c9a", "#ffb8b6"]);

const SVG_TOP = 20;
const SVG_HEIGHT = 240;
const SVG_LEFT = 40;
const SVG_WIDTH = 940;

export const toNum = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

export const yToSvg = (y) => {
  const clamped = Math.max(0, Math.min(100, Number(y)));
  return SVG_TOP + ((100 - clamped) / 100) * SVG_HEIGHT;
};

const toPoints = (samples, valueGetter, span) =>
  samples
    .map((sample, sampleIndex) => {
      const x = SVG_LEFT + (sampleIndex / span) * SVG_WIDTH;
      const y = yToSvg(valueGetter(sample));
      return `${x},${y}`;
    })
    .join(" ");

const round1 = (value) => toNum(value, 0).toFixed(1);

const formatDeviceLabel = (gpuName, totalMb) => {
  const name = String(gpuName || "GPU").trim() || "GPU";
  const totalGiB = toNum(totalMb, 0) / 1024;
  return `${name} · ${totalGiB.toFixed(1)} GB`;
};

export const buildGpuChartData = (series) => {
  const rows = Array.isArray(series) ? series : [];
  const maxSamples = rows.reduce((acc, item) => Math.max(acc, (item?.samples || []).length), 0);
  const span = Math.max(1, maxSamples - 1);

  const lines = [];
  const deviceInfos = [];
  for (let index = 0; index < rows.length; index += 1) {
    const item = rows[index] || {};
    const samples = Array.isArray(item.samples) ? item.samples : [];
    const gpuName = String(item.gpu_name || "").trim() || "GPU";

    const gpuValues = samples.map((sample) => toNum(sample?.utilization_gpu, 0));
    const vramValues = samples.map((sample) => {
      const used = toNum(sample?.memory_used_mb, 0);
      const total = toNum(sample?.memory_total_mb, 0);
      if (total <= 0) return 0;
      return Math.max(0, Math.min(100, (used / total) * 100));
    });

    const gpuKey = `${gpuName}-gpu-${index}`;
    const vramKey = `${gpuName}-vram-${index}`;

    lines.push({
      key: gpuKey,
      color: GPU_LINE_COLORS[index % GPU_LINE_COLORS.length],
      points: toPoints(samples, (sample) => toNum(sample?.utilization_gpu, 0), span),
      label: `${gpuName} 使用率`,
      latest: gpuValues.length ? round1(gpuValues[gpuValues.length - 1]) : "0.0",
      peak: gpuValues.length ? round1(Math.max(...gpuValues)) : "0.0",
      kind: "gpu",
    });

    lines.push({
      key: vramKey,
      color: VRAM_LINE_COLORS[index % VRAM_LINE_COLORS.length],
      points: toPoints(
        samples,
        (sample) => {
          const used = toNum(sample?.memory_used_mb, 0);
          const total = toNum(sample?.memory_total_mb, 0);
          if (total <= 0) return 0;
          return Math.max(0, Math.min(100, (used / total) * 100));
        },
        span
      ),
      label: `${gpuName} 显存占用率`,
      latest: vramValues.length ? round1(vramValues[vramValues.length - 1]) : "0.0",
      peak: vramValues.length ? round1(Math.max(...vramValues)) : "0.0",
      kind: "vram",
    });

    const latestSample = samples.length ? samples[samples.length - 1] : {};
    const totalMb =
      toNum(latestSample?.memory_total_mb, 0) ||
      Math.max(0, ...samples.map((sample) => toNum(sample?.memory_total_mb, 0)));
    deviceInfos.push({
      key: `device-${index}`,
      label: formatDeviceLabel(gpuName, totalMb),
    });
  }

  return {
    lines,
    deviceInfos,
  };
};
