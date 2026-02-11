import { ref } from "vue";

const THEME_MODE_KEY = "mbv_theme_mode";
const VALID_THEME_MODES = new Set(["auto", "dark", "light"]);
const THEME_TRANSITION_ATTR = "data-theme-transition";
const DARK_TO_LIGHT_TRANSITION = "dark-to-light";
const LIGHT_TRANSITION_MS = 3000;

export const useWorkbenchTheme = () => {
  const themeMode = ref("dark");
  const activeTheme = ref("dark");
  let themeTimer = null;
  let transitionTimer = null;

  const resolveThemeByClock = () => {
    try {
      const hour = new Date().getHours();
      if (Number.isNaN(hour)) return "dark";
      return hour >= 18 || hour < 8 ? "dark" : "light";
    } catch (_err) {
      return "dark";
    }
  };

  const resolveTheme = () => {
    if (themeMode.value === "light") return "light";
    if (themeMode.value === "dark") return "dark";
    return resolveThemeByClock();
  };

  const clearTransitionTimer = () => {
    if (!transitionTimer) return;
    clearTimeout(transitionTimer);
    transitionTimer = null;
  };

  const clearThemeTransition = () => {
    clearTransitionTimer();
    document.documentElement.removeAttribute(THEME_TRANSITION_ATTR);
  };

  const runThemeTransition = (fromTheme, toTheme) => {
    clearThemeTransition();
    if (fromTheme !== "dark" || toTheme !== "light") return;

    const root = document.documentElement;
    root.removeAttribute(THEME_TRANSITION_ATTR);
    // Force reflow so repeated dark->light switches can retrigger animation.
    void root.offsetWidth;
    root.setAttribute(THEME_TRANSITION_ATTR, DARK_TO_LIGHT_TRANSITION);
    transitionTimer = setTimeout(() => {
      root.removeAttribute(THEME_TRANSITION_ATTR);
      transitionTimer = null;
    }, LIGHT_TRANSITION_MS);
  };

  const applyTheme = (theme) => {
    const safeTheme = theme === "light" ? "light" : "dark";
    const previousTheme = activeTheme.value;
    activeTheme.value = safeTheme;
    document.documentElement.setAttribute("data-theme", safeTheme);
    runThemeTransition(previousTheme, safeTheme);
  };

  const clearThemeTimer = () => {
    if (!themeTimer) return;
    clearInterval(themeTimer);
    themeTimer = null;
  };

  const setupThemeTimer = () => {
    clearThemeTimer();
    if (themeMode.value !== "auto") return;
    themeTimer = setInterval(() => {
      applyTheme(resolveTheme());
    }, 60 * 1000);
  };

  const onThemeModeChange = (nextMode) => {
    if (typeof nextMode === "string") {
      themeMode.value = nextMode;
    }
    if (!VALID_THEME_MODES.has(themeMode.value)) {
      themeMode.value = "dark";
    }
    try {
      window.localStorage.setItem(THEME_MODE_KEY, themeMode.value);
    } catch (_err) {
      // ignore storage errors
    }
    applyTheme(resolveTheme());
    setupThemeTimer();
  };

  const initTheme = () => {
    try {
      const savedMode = window.localStorage.getItem(THEME_MODE_KEY);
      themeMode.value = VALID_THEME_MODES.has(savedMode) ? savedMode : "dark";
    } catch (_err) {
      themeMode.value = "dark";
    }
    onThemeModeChange();
  };

  const disposeTheme = () => {
    clearThemeTimer();
    clearThemeTransition();
  };

  return {
    themeMode,
    activeTheme,
    onThemeModeChange,
    initTheme,
    disposeTheme,
  };
};
