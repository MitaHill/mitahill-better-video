export const TOP_TAB_FALLBACKS = Object.freeze([
  { key: "enhance", label: "增强" },
  { key: "convert", label: "转换" },
  { key: "transcribe", label: "转录" },
  { key: "download", label: "下载" },
  { key: "admin", label: "管理" },
]);

export const resolveTabs = (tabs) => {
  if (Array.isArray(tabs) && tabs.length) return tabs;
  return TOP_TAB_FALLBACKS;
};

export const computeActiveIndex = (tabs, activeCategory) => {
  const idx = (Array.isArray(tabs) ? tabs : []).findIndex((tab) => tab.key === activeCategory);
  return idx >= 0 ? idx : 0;
};

export const computeSliderStyle = (activeIndex, tabCount) => {
  const safeCount = Math.max(1, Number(tabCount) || 1);
  return {
    width: `calc((100% / ${safeCount}) * 0.62)`,
    left: `calc(${activeIndex} * (100% / ${safeCount}) + ((100% / ${safeCount}) * 0.19))`,
  };
};
