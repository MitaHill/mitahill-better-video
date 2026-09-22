export const CATEGORY_PATH = Object.freeze({
  enhance: "/enhance",
  convert: "/convert",
  transcribe: "/transcribe",
  chain: "/chain",
  admin: "/admin",
});

export const CATEGORY_TABS = Object.freeze([
  { key: "enhance", label: "增强" },
  { key: "convert", label: "转换" },
  { key: "transcribe", label: "转录" },
  { key: "chain", label: "链式" },
  { key: "admin", label: "管理" },
]);

export const getCategoryByPath = (path) => {
  const normalized = (String(path || "").replace(/\/+$/, "") || "/");
  if (normalized === CATEGORY_PATH.convert) return "convert";
  if (normalized === CATEGORY_PATH.transcribe) return "transcribe";
  if (normalized === CATEGORY_PATH.chain) return "chain";
  if (normalized === CATEGORY_PATH.admin) return "admin";
  return "enhance";
};
