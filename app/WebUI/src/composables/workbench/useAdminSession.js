import { reactive, ref } from "vue";

const ADMIN_TOKEN_KEY = "mbv_admin_token";

export const useAdminSession = ({ parseJsonSafe }) => {
  const adminPassword = ref("");
  const auth = reactive({
    token: "",
    sessionId: "",
    expiresAt: "",
    loading: false,
    error: "",
    ready: false,
  });

  const saveToken = (token) => {
    auth.token = String(token || "").trim();
    try {
      if (auth.token) {
        window.localStorage.setItem(ADMIN_TOKEN_KEY, auth.token);
      } else {
        window.localStorage.removeItem(ADMIN_TOKEN_KEY);
      }
    } catch (_err) {
      // ignore storage errors
    }
  };

  const authHeaders = () => {
    if (!auth.token) return {};
    return { Authorization: `Bearer ${auth.token}` };
  };

  const clearAuth = () => {
    saveToken("");
    auth.sessionId = "";
    auth.expiresAt = "";
  };

  const handleAuthedError = (res) => {
    if (res && res.status === 401) {
      clearAuth();
    }
  };

  const initAdminAuth = async () => {
    try {
      const saved = window.localStorage.getItem(ADMIN_TOKEN_KEY);
      saveToken(saved || "");
    } catch (_err) {
      saveToken("");
    }

    if (!auth.token) {
      auth.ready = true;
      return;
    }

    try {
      const res = await fetch("/api/admin/session", { headers: authHeaders() });
      if (!res.ok) {
        clearAuth();
      } else {
        const payload = await parseJsonSafe(res);
        auth.sessionId = payload.session_id || "";
        auth.expiresAt = payload.expires_at || "";
      }
    } catch (_err) {
      clearAuth();
    } finally {
      auth.ready = true;
    }
  };

  const resolveLoginError = (payload) => {
    const errorCode = String(payload?.error_code || "").trim().toLowerCase();
    const rawMessage = String(payload?.error || "").trim();
    if (errorCode === "invalid_password" || rawMessage.toLowerCase() === "invalid password") {
      return "管理密码错误，请重新输入。";
    }
    if (errorCode === "missing_password") {
      return "请输入管理密码。";
    }
    return rawMessage || "登录失败";
  };

  const loginAdmin = async () => {
    auth.error = "";
    auth.loading = true;
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: adminPassword.value || "" }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(resolveLoginError(payload));
      }
      saveToken(payload.token || "");
      auth.sessionId = payload.session_id || "";
      auth.expiresAt = payload.expires_at || "";
      adminPassword.value = "";
      return true;
    } catch (error) {
      auth.error = error.message;
      clearAuth();
      return false;
    } finally {
      auth.loading = false;
    }
  };

  const logoutAdmin = async () => {
    try {
      if (auth.token) {
        await fetch("/api/admin/logout", { method: "POST", headers: authHeaders() });
      }
    } catch (_err) {
      // ignore
    }
    clearAuth();
  };

  return {
    adminPassword,
    auth,
    authHeaders,
    handleAuthedError,
    initAdminAuth,
    loginAdmin,
    logoutAdmin,
  };
};
