import { ref } from "vue";
import { CATEGORY_PATH, getCategoryByPath } from "../../constants/workbench";

export const useWorkbenchCategory = () => {
  const activeCategory = ref("enhance");

  const switchCategory = (category) => {
    const safeCategory = Object.prototype.hasOwnProperty.call(CATEGORY_PATH, category) ? category : "enhance";
    activeCategory.value = safeCategory;
    const targetPath = CATEGORY_PATH[safeCategory] || CATEGORY_PATH.enhance;
    if (window.location.pathname !== targetPath) {
      window.history.pushState({ category: safeCategory }, "", targetPath);
    }
  };

  const syncCategoryFromPath = () => {
    activeCategory.value = getCategoryByPath(window.location.pathname);
  };

  const onPopState = () => {
    syncCategoryFromPath();
  };

  const initCategoryRouting = () => {
    syncCategoryFromPath();
    window.addEventListener("popstate", onPopState);
  };

  const disposeCategoryRouting = () => {
    window.removeEventListener("popstate", onPopState);
  };

  return {
    activeCategory,
    switchCategory,
    initCategoryRouting,
    disposeCategoryRouting,
  };
};
