export const CATEGORY_PATH = Object.freeze({
  enhance: "/enhance",
  convert: "/convert",
  admin: "/admin",
});

export const CATEGORY_TABS = Object.freeze([
  { key: "enhance", label: "视频增强" },
  { key: "convert", label: "视频转换" },
  { key: "admin", label: "后端管理" },
]);

export const getCategoryByPath = (path) => {
  const normalized = (String(path || "").replace(/\/+$/, "") || "/");
  if (normalized === CATEGORY_PATH.convert) return "convert";
  if (normalized === CATEGORY_PATH.admin) return "admin";
  return "enhance";
};
