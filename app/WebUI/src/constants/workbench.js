export const CATEGORY_PATH = Object.freeze({
  enhance: "/enhance",
  convert: "/convert",
  transcribe: "/transcribe",
  chain: "/chain",
  admin: "/admin",
});

// 链式（chain）暂时不放进页签：功能已实现但先搁置，入口隐藏。路由和页面都还在，
// 直接访问 /chain 仍可用于验证；要重新放出来，把 chain 一项加回这里即可。
export const CATEGORY_TABS = Object.freeze([
  { key: "enhance", label: "增强" },
  { key: "convert", label: "转换" },
  { key: "transcribe", label: "转录" },
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
