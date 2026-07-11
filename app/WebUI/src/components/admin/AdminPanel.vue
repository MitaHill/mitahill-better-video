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
            <h2>管理</h2>
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
          :filtered-tree="filteredMenuTree"
          @update:query="onMenuSearchChange"
          @select="onMenuSelect"
          @close="sidebarOpen = false"
        />

        <div class="admin-content">
          <div v-if="activeMenuKey === 'overview'" class="panel admin-card">
            <div class="status-row admin-head-row">
              <h2>任务总览</h2>
              <div class="status-row" style="gap: 8px;">
                <button
                  type="button"
                  :disabled="overview.updatingMaintenanceMode"
                  @click="toggleMaintenanceMode"
                >
                  {{
                    overview.updatingMaintenanceMode
                      ? "切换中..."
                      : overview.maintenanceMode
                        ? "退出维护模式"
                        : "进入维护模式"
                  }}
                </button>
                <button class="secondary" type="button" :disabled="overview.loading" @click="fetchOverview">
                  {{ overview.loading ? "刷新中..." : "刷新" }}
                </button>
              </div>
            </div>
            <AdminOverviewCards :counts="overview.counts" />
            <p class="notice" style="margin-top: 10px;">
              维护模式：{{ overview.maintenanceMode ? "已开启（暂停拉取新任务）" : "关闭" }}
            </p>
            <p class="notice" style="margin-top: 10px;">当前请求识别IP：{{ proxyConfig.resolvedClientIp || '-' }}</p>
          </div>

          <AdminGpuUsageChart
            v-if="activeMenuKey === 'overview'"
            :series="gpuUsage.series"
            :loading="gpuUsage.loading"
            :error="gpuUsage.error"
            :range-seconds="gpuUsage.rangeSeconds"
            :on-range-change="onGpuRangeChange"
            :on-refresh="onGpuRefresh"
          />

          <AdminTaskTable
            v-if="activeMenuKey === 'tasks'"
            :tasks="overview.tasks"
            :status-filter="overview.statusFilter"
            :loading="overview.loading"
            :error="overview.error"
            :on-refresh="fetchOverview"
            :on-cancel-task="onTaskCancel"
            :on-delete-task="onTaskDelete"
            :task-action-loading="taskActionLoading"
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
            v-if="activeMenuKey === 'debug_tests'"
            :loading-model="debugTools.loadingModelTest"
            :model-error="debugTools.modelTestError"
            :model-result="debugTools.modelTestResult"
            :model-steps="debugTools.modelTestSteps"
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
import { filterMenuTree } from "./adminMenu";
import AdminDebugToolsPanel from "./AdminDebugToolsPanel.vue";
import AdminGpuUsageChart from "./AdminGpuUsageChart.vue";
import AdminIpTable from "./AdminIpTable.vue";
import AdminLoginCard from "./AdminLoginCard.vue";
import AdminLogsPanel from "./AdminLogsPanel.vue";
import AdminOverviewCards from "./AdminOverviewCards.vue";
import AdminPasswordForm from "./AdminPasswordForm.vue";
import AdminProxyConfigForm from "./AdminProxyConfigForm.vue";
import AdminSideDrawer from "./AdminSideDrawer.vue";
import AdminTaskTable from "./AdminTaskTable.vue";
import AdminTranscriptionModelPanel from "./AdminTranscriptionModelPanel.vue";
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

const filteredMenuTree = computed(() => filterMenuTree(menuSearch.value));

let timer = null;

const stopTimer = () => {
  if (!timer) return;
  clearInterval(timer);
  timer = null;
};

const needOverviewRefresh = () => ["overview", "tasks", "ips"].includes(activeMenuKey.value);
const needModelDownloadRefresh = () => activeMenuKey.value === "transcribe_cfg_catalog";
const needLogsRefresh = () => activeMenuKey.value === "logs_warn";
const needGpuUsageRefresh = () => activeMenuKey.value === "overview";

const startTimer = () => {
  stopTimer();
  if (!props.active || !auth.token) return;
  timer = setInterval(() => {
    if (needOverviewRefresh()) {
      fetchOverview();
    }
    if (needGpuUsageRefresh()) {
      fetchGpuUsage(gpuUsage.rangeSeconds || 60);
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

const onTaskCancel = async (taskId) => {
  await cancelTaskById(taskId);
};

const onTaskDelete = async (taskId) => {
  await deleteTaskById(taskId);
};

const taskActionLoading = (taskId) => Boolean(overview.taskActionLoading[String(taskId || "")]);

const toggleMaintenanceMode = async () => {
  await setMaintenanceMode(!overview.maintenanceMode);
};

const onGpuRangeChange = async (seconds) => {
  await fetchGpuUsage(seconds);
};

const onGpuRefresh = async () => {
  await fetchGpuUsage(gpuUsage.rangeSeconds || 60);
};

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value;
};

const onMenuSearchChange = (value) => {
  menuSearch.value = value;
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
  if (value === "transcribe_cfg_translation") {
    await fetchTranscriptionConfig();
    return;
  }
  if (value === "transcribe_cfg_catalog") {
    await refreshTranscriptionCatalog();
    return;
  }
  if (value === "debug_tests") {
    await fetchTranscriptionConfig();
    return;
  }
  if (value === "logs_warn") {
    await fetchAdminLogs();
    return;
  }
  if (needOverviewRefresh()) {
    await fetchOverview();
    if (value === "overview") {
      await fetchGpuUsage(gpuUsage.rangeSeconds || 60);
    }
  }
};

const onMenuSelect = async (value) => {
  activeMenuKey.value = value;
};

const flattenMenuKeys = (nodes) => {
  const keys = [];
  const walk = (items) => {
    for (const item of items || []) {
      const children = Array.isArray(item.children) ? item.children : [];
      if (!children.length) {
        keys.push(item.key);
      } else {
        walk(children);
      }
    }
  };
  walk(nodes);
  return keys;
};

watch(filteredMenuTree, (tree) => {
  const keys = flattenMenuKeys(tree);
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
