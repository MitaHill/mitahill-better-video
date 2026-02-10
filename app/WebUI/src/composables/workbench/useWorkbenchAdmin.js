import { reactive, ref } from "vue";

const ADMIN_TOKEN_KEY = "mbv_admin_token";

export const useWorkbenchAdmin = ({ parseJsonSafe }) => {
  const adminPassword = ref("");

  const auth = reactive({
    token: "",
    sessionId: "",
    expiresAt: "",
    loading: false,
    error: "",
    ready: false,
  });

  const overview = reactive({
    loading: false,
    error: "",
    counts: {
      total: 0,
      pending: 0,
      processing: 0,
      completed: 0,
      failed: 0,
    },
    tasks: [],
    ipStats: [],
    statusFilter: "",
    realIpConfig: null,
  });

  const passwordForm = reactive({
    oldPassword: "",
    newPassword: "",
    loading: false,
    error: "",
    message: "",
  });

  const _saveToken = (token) => {
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

  const _authHeaders = () => {
    if (!auth.token) return {};
    return { Authorization: `Bearer ${auth.token}` };
  };

  const _clearAuth = () => {
    _saveToken("");
    auth.sessionId = "";
    auth.expiresAt = "";
  };

  const initAdminAuth = async () => {
    try {
      const saved = window.localStorage.getItem(ADMIN_TOKEN_KEY);
      _saveToken(saved || "");
    } catch (_err) {
      _saveToken("");
    }

    if (!auth.token) {
      auth.ready = true;
      return;
    }

    try {
      const res = await fetch("/api/admin/session", { headers: _authHeaders() });
      if (!res.ok) {
        _clearAuth();
      } else {
        const payload = await parseJsonSafe(res);
        auth.sessionId = payload.session_id || "";
        auth.expiresAt = payload.expires_at || "";
      }
    } catch (_err) {
      _clearAuth();
    } finally {
      auth.ready = true;
    }
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
        throw new Error(payload.error || "登录失败");
      }
      _saveToken(payload.token || "");
      auth.sessionId = payload.session_id || "";
      auth.expiresAt = payload.expires_at || "";
      adminPassword.value = "";
      await fetchOverview();
    } catch (error) {
      auth.error = error.message;
      _clearAuth();
    } finally {
      auth.loading = false;
    }
  };

  const logoutAdmin = async () => {
    try {
      if (auth.token) {
        await fetch("/api/admin/logout", { method: "POST", headers: _authHeaders() });
      }
    } catch (_err) {
      // ignore
    }
    _clearAuth();
  };

  const fetchOverview = async () => {
    if (!auth.token) return;
    overview.error = "";
    overview.loading = true;
    try {
      const query = new URLSearchParams();
      if (overview.statusFilter) query.set("status", overview.statusFilter);
      query.set("limit", "200");
      const res = await fetch(`/api/admin/overview?${query.toString()}`, { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        if (res.status === 401) {
          _clearAuth();
        }
        throw new Error(payload.error || "拉取管理数据失败");
      }
      overview.counts = payload.counts || overview.counts;
      overview.tasks = payload.tasks || [];
      overview.ipStats = payload.ip_stats || [];
      overview.realIpConfig = payload.real_ip_config || null;
    } catch (error) {
      overview.error = error.message;
    } finally {
      overview.loading = false;
    }
  };

  const changeAdminPassword = async () => {
    passwordForm.error = "";
    passwordForm.message = "";
    passwordForm.loading = true;
    try {
      const res = await fetch("/api/admin/password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify({
          old_password: passwordForm.oldPassword,
          new_password: passwordForm.newPassword,
        }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(payload.error || "修改密码失败");
      }
      passwordForm.message = payload.message || "密码已更新，请重新登录";
      passwordForm.oldPassword = "";
      passwordForm.newPassword = "";
      await logoutAdmin();
    } catch (error) {
      passwordForm.error = error.message;
    } finally {
      passwordForm.loading = false;
    }
  };

  return {
    adminPassword,
    auth,
    overview,
    passwordForm,
    initAdminAuth,
    loginAdmin,
    logoutAdmin,
    fetchOverview,
    changeAdminPassword,
  };
};
