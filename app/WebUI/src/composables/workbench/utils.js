export const isFilenameSafe = (name) => {
  if (!name || name.length > 180) return false;
  if (name.includes("/") || name.includes("\\")) return false;
  return !/[\u0000-\u001f\u007f]/.test(name);
};

export const validateFiles = (files) => files.every((f) => isFilenameSafe(f.name));

export const parseJsonSafe = async (res) => {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return res.json();
  const text = await res.text();
  throw new Error(text || "服务返回非JSON响应。");
};

export const formatBool = (value) => (value ? "是" : "否");

const BACKEND_PREFIX_MAP = Object.freeze({
  whisper: "whisper-openai",
  faster_whisper: "fast-whisper",
});

const PREFIX_BACKEND_MAP = Object.freeze({
  "whisper-openai": "whisper",
  "openai-whisper": "whisper",
  whisper: "whisper",
  "fast-whisper": "faster_whisper",
  "faster-whisper": "faster_whisper",
  faster_whisper: "faster_whisper",
});

export const normalizeTranscribeBackend = (backend, fallback = "whisper") => {
  const safe = String(backend || "").trim().toLowerCase();
  if (!safe) return String(fallback || "whisper").trim().toLowerCase();
  return PREFIX_BACKEND_MAP[safe] || safe;
};

export const splitTranscribeModelRef = (modelRef, fallbackBackend = "whisper") => {
  const backendFallback = normalizeTranscribeBackend(fallbackBackend, "whisper");
  const safe = String(modelRef || "").trim().toLowerCase();
  if (!safe) return { backend: backendFallback, modelId: "" };
  if (!safe.includes("/")) return { backend: backendFallback, modelId: safe };

  const [prefix, ...rest] = safe.split("/");
  const modelId = String(rest.join("/") || "").trim().toLowerCase();
  if (!modelId) return { backend: backendFallback, modelId: safe };
  const mapped = normalizeTranscribeBackend(prefix, backendFallback);
  if (!PREFIX_BACKEND_MAP[prefix] && mapped === prefix) return { backend: backendFallback, modelId: safe };
  return { backend: mapped, modelId };
};

export const formatTranscribeModelRef = (backend, modelId) => {
  const safeBackend = normalizeTranscribeBackend(backend, "whisper");
  const prefix = BACKEND_PREFIX_MAP[safeBackend] || safeBackend || "whisper-openai";
  const safeModelId = String(modelId || "").trim().toLowerCase();
  if (!safeModelId) return prefix;
  return `${prefix}/${safeModelId}`;
};
