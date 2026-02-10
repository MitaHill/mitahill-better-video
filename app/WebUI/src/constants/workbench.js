export const CATEGORY_PATH = Object.freeze({
  enhance: "/enhance",
  convert: "/convert",
});

export const CATEGORY_TABS = Object.freeze([
  { key: "enhance", label: "视频增强" },
  { key: "convert", label: "视频转换" },
]);

export const getCategoryByPath = (path) => {
  if (path === CATEGORY_PATH.convert) return "convert";
  return "enhance";
};
