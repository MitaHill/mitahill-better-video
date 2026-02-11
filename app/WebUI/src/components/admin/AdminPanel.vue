<template>
  <div class="admin-layout">
    <AdminLoginCard
      v-if="!auth.token"
      :password="adminPassword"
      :loading="auth.loading"
      :error="auth.error"
      :on-login="loginAdmin"
      @update:password="onPasswordInput"
    />

    <template v-else>
      <div class="panel admin-card admin-toolbar">
        <div class="status-row admin-head-row">
          <div class="status-row" style="gap: 8px;">
            <button class="secondary" type="button" @click="toggleSidebar">{{ sidebarOpen ? "隐藏菜单" : "显示菜单" }}</button>
            <h2>后端管理</h2>
          </div>
          <div class="status-row" style="gap: 8px;">
            <span class="notice">会话有效期：{{ auth.expiresAt || '-' }}</span>
            <button class="secondary" @click="logoutAdmin">退出登录</button>
          </div>
        </div>
      </div>

      <div class="admin-shell" :class="{ 'sidebar-collapsed': !sidebarOpen }">
        <AdminSideDrawer
          :open="sidebarOpen"
          :query="menuSearch"
          :active-key="activeMenuKey"
          :filtered-groups="filteredMenuGroups"
          @update:query="onMenuSearchChange"
          @select="onMenuSelect"
          @close="sidebarOpen = false"
        />

        <div class="admin-content">
          <div v-if="activeMenuKey === 'overview'" class="panel admin-card">
            <h2>任务总览</h2>
            <AdminOverviewCards :counts="overview.counts" />
            <p class="notice" style="margin-top: 10px;">当前请求识别IP：{{ proxyConfig.resolvedClientIp || '-' }}</p>
          </div>

          <AdminTaskTable
            v-if="activeMenuKey === 'tasks'"
            :tasks="overview.tasks"
            :status-filter="overview.statusFilter"
            :loading="overview.loading"
            :error="overview.error"
            :on-refresh="fetchOverview"
            @update:status-filter="onStatusFilterChange"
          />

          <AdminIpTable v-if="activeMenuKey === 'ips'" :ip-stats="overview.ipStats" />

          <AdminProxyConfigForm
            v-if="activeMenuKey === 'proxy'"
            :trusted-proxies="proxyConfig.trustedProxies"
            :resolved-client-ip="proxyConfig.resolvedClientIp"
            :from-env-default="proxyConfig.fromEnvDefault"
            :loading="proxyConfig.loading"
            :error="proxyConfig.error"
            :message="proxyConfig.message"
            :on-save="updateRealIpConfig"
            @update:trusted-proxies="onProxyInput"
          />

          <AdminPasswordForm
            v-if="activeMenuKey === 'password'"
            :old-password="passwordForm.oldPassword"
            :new-password="passwordForm.newPassword"
            :loading="passwordForm.loading"
            :error="passwordForm.error"
            :message="passwordForm.message"
            :on-change-password="changeAdminPassword"
            @update:old-password="onOldPasswordInput"
            @update:new-password="onNewPasswordInput"
          />

          <AdminConstraintEditor
            v-if="activeMenuKey === 'constraints_enhance'"
            category-key="enhance"
            category-label="视频增强"
            :category-config="categoryConstraint('enhance')"
            :loading="formConstraints.loading"
            :error="formConstraints.error"
            :message="formConstraints.message"
            :on-save="updateFormConstraintsCategory"
          />

          <AdminConstraintEditor
            v-if="activeMenuKey === 'constraints_convert'"
            category-key="convert"
            category-label="视频转换"
            :category-config="categoryConstraint('convert')"
            :loading="formConstraints.loading"
            :error="formConstraints.error"
            :message="formConstraints.message"
            :on-save="updateFormConstraintsCategory"
          />

          <AdminConstraintEditor
            v-if="activeMenuKey === 'constraints_transcribe'"
            category-key="transcribe"
            category-label="视频转录"
            :category-config="categoryConstraint('transcribe')"
            :loading="formConstraints.loading"
            :error="formConstraints.error"
            :message="formConstraints.message"
            :on-save="updateFormConstraintsCategory"
          />

          <AdminTranscriptionModelSettingsForm
            v-if="activeMenuKey === 'transcribe_cfg_model'"
            :config-data="transcriptionConfig.data || {}"
            :loading="transcriptionConfig.loading"
            :error="transcriptionConfig.error"
            :message="transcriptionConfig.message"
            :on-save="saveTranscriptionModelConfig"
          />

          <AdminTranslationSettingsForm
            v-if="activeMenuKey === 'transcribe_cfg_translation'"
            :config-data="transcriptionConfig.data || {}"
            :loading="transcriptionConfig.loading"
            :error="transcriptionConfig.error"
            :message="transcriptionConfig.message"
            :on-save="saveTranslationConfig"
          />

          <AdminTranscriptionModelPanel
            v-if="activeMenuKey === 'transcribe_cfg_catalog'"
            :models="transcriptionModels.items"
            :jobs="transcriptionModels.jobs"
            :loading="transcriptionModels.loading"
            :error="transcriptionModels.error"
            :message="transcriptionModels.message"
            :on-refresh="refreshTranscriptionCatalog"
            :on-download="startTranscriptionModelDownload"
            :on-cancel-job="cancelTranscriptionModelDownloadJob"
            :on-delete-job="deleteTranscriptionModelDownloadJob"
          />

          <AdminDebugToolsPanel
            v-if="activeMenuKey === 'debug_model' || activeMenuKey === 'debug_translate'"
            :loading-model="debugTools.loadingModelTest"
            :model-error="debugTools.modelTestError"
            :model-result="debugTools.modelTestResult"
            :model-steps="debugTools.modelTestSteps"
            :transcription-models="transcriptionModels.items"
            :transcription-config="transcriptionConfig.data || {}"
            :loading-translation="debugTools.loadingTranslationTest"
            :translation-error="debugTools.translationTestError"
            :translation-result="debugTools.translationTestResult"
            :on-test-model="testTranscriptionModel"
            :on-test-translation="testTranslationProvider"
          />

          <AdminLogsPanel
            v-if="activeMenuKey === 'logs_warn'"
            :logs="logsView.logs"
            :loading="logsView.loading"
            :error="logsView.error"
            :min-level="logsView.minLevel"
            :keyword="logsView.keyword"
            :logger-name="logsView.loggerName"
            :on-refresh="fetchAdminLogs"
            @update:min-level="onLogsMinLevelChange"
            @update:keyword="onLogsKeywordChange"
            @update:logger-name="onLogsLoggerChange"
          />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { useWorkbenchAdmin } from "../../composables/workbench/useWorkbenchAdmin";
import { parseJsonSafe } from "../../composables/workbench/utils";
import AdminConstraintEditor from "./AdminConstraintEditor.vue";
import AdminDebugToolsPanel from "./AdminDebugToolsPanel.vue";
import AdminIpTable from "./AdminIpTable.vue";
import AdminLoginCard from "./AdminLoginCard.vue";
import AdminLogsPanel from "./AdminLogsPanel.vue";
import AdminOverviewCards from "./AdminOverviewCards.vue";
import AdminPasswordForm from "./AdminPasswordForm.vue";
import AdminProxyConfigForm from "./AdminProxyConfigForm.vue";
import AdminSideDrawer from "./AdminSideDrawer.vue";
import AdminTaskTable from "./AdminTaskTable.vue";
import AdminTranscriptionModelPanel from "./AdminTranscriptionModelPanel.vue";
import AdminTranscriptionModelSettingsForm from "./AdminTranscriptionModelSettingsForm.vue";
import AdminTranslationSettingsForm from "./AdminTranslationSettingsForm.vue";

const props = defineProps({
  active: {
    type: Boolean,
    required: true,
  },
});

const {
  adminPassword,
  auth,
  overview,
  passwordForm,
  proxyConfig,
  formConstraints,
  transcriptionConfig,
  transcriptionModels,
  debugTools,
  logsView,
  initAdminAuth,
  loginAdmin,
  logoutAdmin,
  fetchOverview,
  fetchRealIpConfig,
  updateRealIpConfig,
  changeAdminPassword,
  fetchFormConstraintsConfig,
  updateFormConstraintsCategory,
  fetchTranscriptionConfig,
  updateTranscriptionConfig,
  fetchTranscriptionModels,
  fetchModelDownloadJobs,
  startModelDownload,
  cancelModelDownloadJob,
  deleteModelDownloadJob,
  testTranscriptionModel,
  testTranslationProvider,
  fetchAdminLogs,
} = useWorkbenchAdmin({ parseJsonSafe });

const sidebarOpen = ref(true);
const menuSearch = ref("");
const activeMenuKey = ref("overview");

const menuGroups = Object.freeze([
  {
    key: "monitoring",
    label: "任务监控",
    keywords: "monitor overview task ip 监控 总览 状态 统计",
    children: Object.freeze([
      { key: "overview", label: "任务总览", keywords: "overview summary 任务 总览" },
      { key: "tasks", label: "任务状态浏览", keywords: "task queue processing 任务 状态" },
      { key: "ips", label: "访问IP统计", keywords: "ip ipv6 stats 访问 统计" },
    ]),
  },
  {
    key: "network",
    label: "网络配置",
    keywords: "proxy trusted frp nginx 代理 网络",
    children: Object.freeze([
      { key: "proxy", label: "受信代理配置", keywords: "proxy trusted frp nginx 代理" },
    ]),
  },
  {
    key: "transcribe_sources",
    label: "转录源设置",
    keywords: "transcribe whisper faster translator model download 转录 模型 翻译",
    children: Object.freeze([
      { key: "transcribe_cfg_model", label: "转录模型设置", keywords: "transcribe whisper faster 模型 设置" },
      { key: "transcribe_cfg_translation", label: "翻译源设置", keywords: "translate ollama openai 翻译 源" },
      { key: "transcribe_cfg_catalog", label: "模型目录与下载", keywords: "model catalog aria2 hash warmup 下载 校验 热身" },
    ]),
  },
  {
    key: "constraints",
    label: "参数约束",
    keywords: "constraints policy lock 参数 约束 锁 范围",
    children: Object.freeze([
      { key: "constraints_enhance", label: "增强参数约束", keywords: "enhance constraints 参数 约束 锁 范围" },
      { key: "constraints_convert", label: "转换参数约束", keywords: "convert constraints 参数 约束 锁 范围" },
      { key: "constraints_transcribe", label: "转录参数约束", keywords: "transcribe constraints 参数 约束 锁 范围 whisper subtitle" },
    ]),
  },
  {
    key: "debug",
    label: "调试工具",
    keywords: "debug test transcription translator 调试 测试",
    children: Object.freeze([
      { key: "debug_model", label: "测试转录模型", keywords: "debug transcribe model whisper 调试 转录 模型" },
      { key: "debug_translate", label: "测试翻译源", keywords: "debug translate provider 调试 翻译 源" },
    ]),
  },
  {
    key: "logs",
    label: "日志",
    keywords: "log warn error warning 日志",
    children: Object.freeze([
      { key: "logs_warn", label: "系统日志", keywords: "log warn error warning 系统 日志" },
    ]),
  },
  {
    key: "security",
    label: "安全设置",
    keywords: "password security 密码 安全",
    children: Object.freeze([
      { key: "password", label: "修改管理密码", keywords: "password security 密码 安全" },
    ]),
  },
]);

const fuzzyIncludes = (text, query) => {
  const source = String(text || "").toLowerCase();
  const target = String(query || "").toLowerCase().trim();
  if (!target) return true;
  if (source.includes(target)) return true;
  let i = 0;
  for (const ch of source) {
    if (ch === target[i]) i += 1;
    if (i >= target.length) return true;
  }
  return false;
};

const filteredMenuGroups = computed(() => {
  const query = menuSearch.value.trim();
  if (!query) return menuGroups;

  const out = [];
  for (const group of menuGroups) {
    const groupTarget = `${group.label} ${group.keywords || ""}`;
    const groupMatched = fuzzyIncludes(groupTarget, query);
    if (groupMatched) {
      out.push(group);
      continue;
    }
    const children = group.children.filter((item) => {
      const target = `${item.label} ${item.keywords || ""}`;
      return fuzzyIncludes(target, query);
    });
    if (children.length) {
      out.push({ ...group, children });
    }
  }
  return out;
});

let timer = null;

const stopTimer = () => {
  if (!timer) return;
  clearInterval(timer);
  timer = null;
};

const needOverviewRefresh = () => ["overview", "tasks", "ips"].includes(activeMenuKey.value);
const needModelDownloadRefresh = () => activeMenuKey.value === "transcribe_cfg_catalog";
const needLogsRefresh = () => activeMenuKey.value === "logs_warn";

const startTimer = () => {
  stopTimer();
  if (!props.active || !auth.token) return;
  timer = setInterval(() => {
    if (needOverviewRefresh()) {
      fetchOverview();
    }
    if (needModelDownloadRefresh()) {
      fetchModelDownloadJobs();
    }
    if (needLogsRefresh()) {
      fetchAdminLogs();
    }
  }, 5000);
};

const onPasswordInput = (value) => {
  adminPassword.value = value;
};

const onOldPasswordInput = (value) => {
  passwordForm.oldPassword = value;
};

const onNewPasswordInput = (value) => {
  passwordForm.newPassword = value;
};

const onProxyInput = (value) => {
  proxyConfig.trustedProxies = value;
};

const onStatusFilterChange = (value) => {
  overview.statusFilter = value;
  fetchOverview();
};

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value;
};

const onMenuSearchChange = (value) => {
  menuSearch.value = value;
};

const saveTranscriptionModelConfig = async (payload) => {
  await updateTranscriptionConfig(payload, "转录模型配置已保存");
  await fetchTranscriptionConfig();
};

const saveTranslationConfig = async (payload) => {
  await updateTranscriptionConfig(payload, "翻译源配置已保存");
  await fetchTranscriptionConfig();
};

const refreshTranscriptionCatalog = async () => {
  await fetchTranscriptionModels();
  await fetchModelDownloadJobs();
};

const startTranscriptionModelDownload = async (backend, modelId) => {
  await startModelDownload(backend, modelId);
  await fetchModelDownloadJobs();
};

const cancelTranscriptionModelDownloadJob = async (jobId) => {
  await cancelModelDownloadJob(jobId);
  await fetchModelDownloadJobs();
};

const deleteTranscriptionModelDownloadJob = async (jobId) => {
  await deleteModelDownloadJob(jobId);
  await fetchModelDownloadJobs();
};

const onLogsMinLevelChange = (value) => {
  logsView.minLevel = value;
  fetchAdminLogs();
};

const onLogsKeywordChange = (value) => {
  logsView.keyword = value;
  fetchAdminLogs();
};

const onLogsLoggerChange = (value) => {
  logsView.loggerName = value;
  fetchAdminLogs();
};

const loadByMenuKey = async (value) => {
  if (value === "proxy") {
    await fetchRealIpConfig();
    return;
  }
  if (String(value).startsWith("constraints_")) {
    await fetchFormConstraintsConfig();
    return;
  }
  if (value === "transcribe_cfg_model" || value === "transcribe_cfg_translation") {
    await fetchTranscriptionConfig();
    return;
  }
  if (value === "transcribe_cfg_catalog") {
    await refreshTranscriptionCatalog();
    return;
  }
  if (value === "debug_model") {
    await fetchTranscriptionConfig();
    await fetchTranscriptionModels();
    return;
  }
  if (value === "logs_warn") {
    await fetchAdminLogs();
    return;
  }
  if (needOverviewRefresh()) {
    await fetchOverview();
  }
};

const onMenuSelect = async (value) => {
  activeMenuKey.value = value;
};

const categoryConstraint = (categoryKey) => {
  return formConstraints?.data?.categories?.[categoryKey] || { global_lock: "free", fields: {} };
};

const flattenMenuKeys = (groups) => {
  const keys = [];
  for (const group of groups || []) {
    for (const item of group.children || []) {
      keys.push(item.key);
    }
  }
  return keys;
};

watch(filteredMenuGroups, (groups) => {
  const keys = flattenMenuKeys(groups);
  if (!keys.length) return;
  const hasActive = keys.includes(activeMenuKey.value);
  if (!hasActive) {
    activeMenuKey.value = keys[0];
  }
});

watch(
  () => props.active,
  async (isActive) => {
    if (!isActive) {
      stopTimer();
      return;
    }
    if (auth.token) {
      await loadByMenuKey(activeMenuKey.value);
    }
    startTimer();
  }
);

watch(
  () => auth.token,
  async (token) => {
    if (token && props.active) {
      await loadByMenuKey(activeMenuKey.value);
    }
    startTimer();
  }
);

watch(activeMenuKey, async (nextKey) => {
  if (!auth.token || !props.active) return;
  await loadByMenuKey(nextKey);
});

onMounted(async () => {
  await initAdminAuth();
  if (props.active && auth.token) {
    await loadByMenuKey(activeMenuKey.value);
  }
  startTimer();
});

onUnmounted(() => {
  stopTimer();
});
</script>
