import { reactive } from "vue";
import { useAdminSession } from "./useAdminSession";

export const useWorkbenchAdmin = ({ parseJsonSafe }) => {
  const {
    adminPassword,
    auth,
    authHeaders,
    handleAuthedError,
    initAdminAuth,
    loginAdmin: loginAdminSession,
    logoutAdmin,
  } = useAdminSession({ parseJsonSafe });

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
    maintenanceMode: false,
    updatingMaintenanceMode: false,
    taskActionLoading: {},
  });

  const gpuUsage = reactive({
    loading: false,
    error: "",
    rangeSeconds: 60,
    series: [],
  });

  const passwordForm = reactive({
    oldPassword: "",
    newPassword: "",
    loading: false,
    error: "",
    message: "",
  });

  const proxyConfig = reactive({
    trustedProxies: "",
    loading: false,
    error: "",
    message: "",
    fromEnvDefault: "",
    resolvedClientIp: "",
  });

  const transcriptionConfig = reactive({
    loading: false,
    error: "",
    message: "",
    data: null,
  });

  const transcriptionModels = reactive({
    loading: false,
    error: "",
    message: "",
    items: [],
    jobs: [],
    activeJobId: "",
  });

  const debugTools = reactive({
    loadingModelTest: false,
    modelTestError: "",
    modelTestResult: null,
    modelTestSteps: [],
    loadingTranslationTest: false,
    translationTestError: "",
    translationTestResult: null,
  });

  const logsView = reactive({
    loading: false,
    error: "",
    logs: [],
    minLevel: "WARNING",
    keyword: "",
    loggerName: "",
  });

  const _authHeaders = () => {
    return authHeaders();
  };

  const _handleAuthedError = (res) => {
    handleAuthedError(res);
  };

  const loginAdmin = async () => {
    const ok = await loginAdminSession();
    if (ok) {
      await fetchOverview();
      await fetchGpuUsage(60);
      await fetchAdminLogs();
    }
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
        _handleAuthedError(res);
        throw new Error(payload.error || "拉取管理数据失败");
      }
      overview.counts = payload.counts || overview.counts;
      overview.tasks = payload.tasks || [];
      overview.ipStats = payload.ip_stats || [];
      overview.realIpConfig = payload.real_ip_config || null;
      overview.maintenanceMode = Boolean(payload.maintenance_mode);
      if (overview.realIpConfig) {
        proxyConfig.trustedProxies = overview.realIpConfig.trusted_proxies || "";
        proxyConfig.resolvedClientIp = overview.realIpConfig.resolved_client_ip || "";
      }
    } catch (error) {
      overview.error = error.message;
    } finally {
      overview.loading = false;
    }
  };

  const setMaintenanceMode = async (enabled) => {
    if (!auth.token) return;
    overview.updatingMaintenanceMode = true;
    overview.error = "";
    try {
      const res = await fetch("/api/admin/maintenance-mode", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify({ enabled: Boolean(enabled) }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "更新维护模式失败");
      }
      overview.maintenanceMode = Boolean(payload.enabled);
      await fetchOverview();
    } catch (error) {
      overview.error = error.message;
    } finally {
      overview.updatingMaintenanceMode = false;
    }
  };

  const cancelTaskById = async (taskId) => {
    const safeTaskId = String(taskId || "").trim();
    if (!auth.token || !safeTaskId) return;
    overview.error = "";
    overview.taskActionLoading[safeTaskId] = true;
    try {
      const res = await fetch(`/api/admin/tasks/${encodeURIComponent(safeTaskId)}/cancel`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify({ reason: "已取消（管理员操作）" }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "取消任务失败");
      }
      await fetchOverview();
    } catch (error) {
      overview.error = error.message;
    } finally {
      overview.taskActionLoading[safeTaskId] = false;
    }
  };

  const deleteTaskById = async (taskId) => {
    const safeTaskId = String(taskId || "").trim();
    if (!auth.token || !safeTaskId) return;
    overview.error = "";
    overview.taskActionLoading[safeTaskId] = true;
    try {
      const res = await fetch(`/api/admin/tasks/${encodeURIComponent(safeTaskId)}`, {
        method: "DELETE",
        headers: _authHeaders(),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "删除任务失败");
      }
      await fetchOverview();
    } catch (error) {
      overview.error = error.message;
    } finally {
      overview.taskActionLoading[safeTaskId] = false;
    }
  };

  const fetchGpuUsage = async (seconds = gpuUsage.rangeSeconds || 60) => {
    if (!auth.token) return;
    gpuUsage.loading = true;
    gpuUsage.error = "";
    try {
      const safeSeconds = Math.max(10, Math.min(24 * 3600, Number(seconds || 60)));
      gpuUsage.rangeSeconds = safeSeconds;
      const query = new URLSearchParams();
      query.set("seconds", String(safeSeconds));
      const res = await fetch(`/api/admin/gpu-usage?${query.toString()}`, { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取GPU使用率失败");
      }
      gpuUsage.series = Array.isArray(payload.series) ? payload.series : [];
    } catch (error) {
      gpuUsage.error = error.message;
    } finally {
      gpuUsage.loading = false;
    }
  };

  const fetchRealIpConfig = async () => {
    if (!auth.token) return;
    proxyConfig.error = "";
    proxyConfig.message = "";
    proxyConfig.loading = true;
    try {
      const res = await fetch("/api/admin/config/real-ip", { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取代理配置失败");
      }
      proxyConfig.trustedProxies = payload.trusted_proxies || "";
      proxyConfig.fromEnvDefault = payload.from_env_default || "";
      proxyConfig.resolvedClientIp = payload.resolved_client_ip || "";
    } catch (error) {
      proxyConfig.error = error.message;
    } finally {
      proxyConfig.loading = false;
    }
  };

  const updateRealIpConfig = async () => {
    if (!auth.token) return;
    proxyConfig.error = "";
    proxyConfig.message = "";
    proxyConfig.loading = true;
    try {
      const res = await fetch("/api/admin/config/real-ip", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify({
          trusted_proxies: proxyConfig.trustedProxies || "",
        }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "保存代理配置失败");
      }
      proxyConfig.trustedProxies = payload.trusted_proxies || proxyConfig.trustedProxies;
      proxyConfig.message = "受信代理配置已更新";
      await fetchOverview();
    } catch (error) {
      proxyConfig.error = error.message;
    } finally {
      proxyConfig.loading = false;
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
        _handleAuthedError(res);
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

  const fetchTranscriptionConfig = async () => {
    if (!auth.token) return;
    transcriptionConfig.loading = true;
    transcriptionConfig.error = "";
    transcriptionConfig.message = "";
    try {
      const res = await fetch("/api/admin/config/transcription-sources", { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取转录源配置失败");
      }
      transcriptionConfig.data = payload || null;
    } catch (error) {
      transcriptionConfig.error = error.message;
    } finally {
      transcriptionConfig.loading = false;
    }
  };

  const updateTranscriptionConfig = async (patchPayload, messageText = "配置已保存") => {
    if (!auth.token) return;
    transcriptionConfig.loading = true;
    transcriptionConfig.error = "";
    transcriptionConfig.message = "";
    try {
      const res = await fetch("/api/admin/config/transcription-sources", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify(patchPayload || {}),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "保存转录源配置失败");
      }
      transcriptionConfig.data = payload.config || transcriptionConfig.data;
      transcriptionConfig.message = messageText;
    } catch (error) {
      transcriptionConfig.error = error.message;
    } finally {
      transcriptionConfig.loading = false;
    }
  };

  const fetchTranscriptionModels = async () => {
    if (!auth.token) return;
    transcriptionModels.loading = true;
    transcriptionModels.error = "";
    try {
      const res = await fetch("/api/admin/transcription/models", { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取模型目录失败");
      }
      transcriptionModels.items = payload.models || [];
    } catch (error) {
      transcriptionModels.error = error.message;
    } finally {
      transcriptionModels.loading = false;
    }
  };

  const fetchModelDownloadJobs = async () => {
    if (!auth.token) return;
    try {
      const res = await fetch("/api/admin/transcription/models/downloads?limit=80", { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取下载任务失败");
      }
      transcriptionModels.jobs = payload.jobs || [];
    } catch (error) {
      transcriptionModels.error = error.message;
    }
  };

  const fetchModelDownloadJob = async (jobId) => {
    if (!auth.token || !jobId) return null;
    const res = await fetch(`/api/admin/transcription/models/downloads/${encodeURIComponent(jobId)}`, {
      headers: _authHeaders(),
    });
    const payload = await parseJsonSafe(res);
    if (!res.ok) {
      _handleAuthedError(res);
      throw new Error(payload.error || "读取下载任务状态失败");
    }
    return payload.job || null;
  };

  const startModelDownload = async (backend, modelId) => {
    if (!auth.token) return;
    transcriptionModels.error = "";
    transcriptionModels.message = "";
    try {
      const res = await fetch("/api/admin/transcription/models/download", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ..._authHeaders(),
        },
        body: JSON.stringify({ backend, model_id: modelId }),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "启动下载失败");
      }
      const job = payload.job || {};
      transcriptionModels.activeJobId = job.job_id || "";
      transcriptionModels.message = `已启动下载任务: ${job.job_id || "-"}`;
      await fetchModelDownloadJobs();
    } catch (error) {
      transcriptionModels.error = error.message;
    }
  };

  const removeTranscriptionModel = async (backend, modelId) => {
    if (!auth.token || !backend || !modelId) return;
    transcriptionModels.error = "";
    transcriptionModels.message = "";
    try {
      const res = await fetch(
        `/api/admin/transcription/models/${encodeURIComponent(backend)}/${encodeURIComponent(modelId)}`,
        {
          method: "DELETE",
          headers: _authHeaders(),
        }
      );
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "移除模型失败");
      }
      transcriptionModels.message = `已移除模型: ${backend}/${modelId}`;
      await fetchTranscriptionModels();
    } catch (error) {
      transcriptionModels.error = error.message;
    }
  };

  const cancelModelDownloadJob = async (jobId) => {
    if (!auth.token || !jobId) return;
    transcriptionModels.error = "";
    transcriptionModels.message = "";
    try {
      const res = await fetch(`/api/admin/transcription/models/downloads/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
        headers: _authHeaders(),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "取消下载任务失败");
      }
      transcriptionModels.message = `已取消任务: ${jobId}`;
      await fetchModelDownloadJobs();
    } catch (error) {
      transcriptionModels.error = error.message;
    }
  };

  const deleteModelDownloadJob = async (jobId) => {
    if (!auth.token || !jobId) return;
    transcriptionModels.error = "";
    transcriptionModels.message = "";
    try {
      const res = await fetch(`/api/admin/transcription/models/downloads/${encodeURIComponent(jobId)}`, {
        method: "DELETE",
        headers: _authHeaders(),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "删除下载任务失败");
      }
      transcriptionModels.message = `已删除任务: ${jobId}`;
      await fetchModelDownloadJobs();
    } catch (error) {
      transcriptionModels.error = error.message;
    }
  };

  const _createModelTestSteps = () => [
    {
      key: "resolve",
      label: "目标解析",
      status: "pending",
      message: "等待执行",
      details: null,
    },
    {
      key: "hash",
      label: "HASH 校验",
      status: "pending",
      message: "等待执行",
      details: null,
    },
    {
      key: "warmup",
      label: "GPU 热身识别 5 秒静音音频",
      status: "pending",
      message: "等待执行",
      details: null,
    },
  ];

  const _updateModelTestStep = (stepKey, patch) => {
    const idx = debugTools.modelTestSteps.findIndex((item) => item.key === stepKey);
    if (idx < 0) return;
    debugTools.modelTestSteps[idx] = {
      ...debugTools.modelTestSteps[idx],
      ...(patch || {}),
    };
  };

  const _buildStepMessage = (stepName, stepPayload) => {
    const payload = stepPayload || {};
    const explicit = String(payload.message || "").trim();
    if (explicit) return explicit;
    if (stepName === "resolve") {
      const checks = payload.checks || [];
      const first = checks[0] || {};
      return String(first.message || (payload.ok ? "目标解析完成" : "目标解析失败"));
    }
    if (stepName === "hash") {
      const checks = payload.checks || [];
      const failed = checks.find((item) => String(item.status || "").toLowerCase() === "failed");
      if (failed && failed.message) return String(failed.message);
      return payload.ok ? "HASH 校验通过" : "HASH 校验失败";
    }
    if (stepName === "warmup") {
      return payload.ok ? "GPU 热身成功" : "GPU 热身失败";
    }
    return payload.ok ? "通过" : "失败";
  };

  const _applyModelTestPayload = (payload) => {
    const steps = (payload && payload.steps) || [];
    for (const step of steps) {
      const name = String(step.name || "").trim().toLowerCase();
      if (!name) continue;
      _updateModelTestStep(name, {
        status: step.ok ? "passed" : "failed",
        message: _buildStepMessage(name, step),
        details: step,
      });
    }
  };

  const _requestTranscriptionModelTest = async (mode, target = null) => {
    const payloadBody = { mode };
    if (target && target.backend && target.modelId) {
      payloadBody.backend = String(target.backend || "").trim().toLowerCase();
      payloadBody.model_id = String(target.modelId || "").trim().toLowerCase();
    }
    const res = await fetch("/api/admin/debug/test-transcription-model", {
      method: "POST",
      headers: {
        ..._authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payloadBody),
    });
    const payload = await parseJsonSafe(res);
    if (!res.ok) {
      _handleAuthedError(res);
    }
    return {
      ok: res.ok,
      payload: payload || {},
    };
  };

  const testTranscriptionModel = async (target = null) => {
    if (!auth.token) return;
    debugTools.loadingModelTest = true;
    debugTools.modelTestError = "";
    debugTools.modelTestResult = null;
    debugTools.modelTestSteps = _createModelTestSteps();

    try {
      const targetLabel =
        target && target.backend && target.modelId
          ? `${String(target.backend).toLowerCase()}/${String(target.modelId).toLowerCase()}`
          : "管理配置中的当前目标";
      _updateModelTestStep("resolve", { status: "running", message: `正在解析测试目标：${targetLabel}` });
      _updateModelTestStep("hash", { status: "running", message: "正在校验模型 HASH..." });
      const hashRes = await _requestTranscriptionModelTest("hash", target);
      _applyModelTestPayload(hashRes.payload);
      debugTools.modelTestResult = hashRes.payload;
      if (!hashRes.ok || !hashRes.payload.ok) {
        _updateModelTestStep("warmup", { status: "pending", message: "未执行（前置校验失败）" });
        throw new Error(hashRes.payload.error || "HASH 校验失败");
      }

      _updateModelTestStep("warmup", { status: "running", message: "正在进行 GPU 热身识别..." });
      const warmupRes = await _requestTranscriptionModelTest("warmup", target);
      _applyModelTestPayload(warmupRes.payload);
      debugTools.modelTestResult = warmupRes.payload;
      if (!warmupRes.ok || !warmupRes.payload.ok) {
        throw new Error(warmupRes.payload.error || "GPU 热身失败");
      }
    } catch (error) {
      debugTools.modelTestError = error.message;
    } finally {
      debugTools.loadingModelTest = false;
    }
  };

  const testTranslationProvider = async () => {
    if (!auth.token) return;
    debugTools.loadingTranslationTest = true;
    debugTools.translationTestError = "";
    debugTools.translationTestResult = null;
    try {
      const res = await fetch("/api/admin/debug/test-translation-provider", {
        method: "POST",
        headers: _authHeaders(),
      });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        debugTools.translationTestResult = payload || null;
        throw new Error(payload.error || "翻译源测试失败");
      }
      debugTools.translationTestResult = payload;
    } catch (error) {
      debugTools.translationTestError = error.message;
    } finally {
      debugTools.loadingTranslationTest = false;
    }
  };

  const fetchAdminLogs = async () => {
    if (!auth.token) return;
    logsView.loading = true;
    logsView.error = "";
    try {
      const query = new URLSearchParams();
      query.set("limit", "200");
      query.set("min_level", logsView.minLevel || "WARNING");
      if (logsView.keyword) query.set("q", logsView.keyword);
      if (logsView.loggerName) query.set("logger", logsView.loggerName);

      const res = await fetch(`/api/admin/logs?${query.toString()}`, { headers: _authHeaders() });
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        _handleAuthedError(res);
        throw new Error(payload.error || "读取日志失败");
      }
      logsView.logs = payload.logs || [];
    } catch (error) {
      logsView.error = error.message;
    } finally {
      logsView.loading = false;
    }
  };

  return {
    adminPassword,
    auth,
    overview,
    gpuUsage,
    passwordForm,
    proxyConfig,
    transcriptionConfig,
    transcriptionModels,
    debugTools,
    logsView,
    initAdminAuth,
    loginAdmin,
    logoutAdmin,
    fetchOverview,
    setMaintenanceMode,
    cancelTaskById,
    deleteTaskById,
    fetchGpuUsage,
    fetchRealIpConfig,
    updateRealIpConfig,
    changeAdminPassword,
    fetchTranscriptionConfig,
    updateTranscriptionConfig,
    fetchTranscriptionModels,
    fetchModelDownloadJobs,
    fetchModelDownloadJob,
    startModelDownload,
    removeTranscriptionModel,
    cancelModelDownloadJob,
    deleteModelDownloadJob,
    testTranscriptionModel,
    testTranslationProvider,
    fetchAdminLogs,
  };
};
