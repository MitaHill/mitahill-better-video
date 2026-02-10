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
          :items="menuItems"
          :active-key="activeMenuKey"
          :filtered-items="filteredMenuItems"
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
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";

import { useWorkbenchAdmin } from "../../composables/workbench/useWorkbenchAdmin";
import { parseJsonSafe } from "../../composables/workbench/utils";
import AdminIpTable from "./AdminIpTable.vue";
import AdminLoginCard from "./AdminLoginCard.vue";
import AdminOverviewCards from "./AdminOverviewCards.vue";
import AdminPasswordForm from "./AdminPasswordForm.vue";
import AdminProxyConfigForm from "./AdminProxyConfigForm.vue";
import AdminSideDrawer from "./AdminSideDrawer.vue";
import AdminTaskTable from "./AdminTaskTable.vue";

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
  initAdminAuth,
  loginAdmin,
  logoutAdmin,
  fetchOverview,
  fetchRealIpConfig,
  updateRealIpConfig,
  changeAdminPassword,
} = useWorkbenchAdmin({ parseJsonSafe });

const sidebarOpen = ref(true);
const menuSearch = ref("");
const activeMenuKey = ref("overview");

const menuItems = Object.freeze([
  { key: "overview", label: "任务总览", keywords: "overview summary 任务 总览" },
  { key: "tasks", label: "任务状态浏览", keywords: "task queue processing 任务 状态" },
  { key: "ips", label: "访问IP统计", keywords: "ip ipv6 stats 访问 统计" },
  { key: "proxy", label: "受信代理配置", keywords: "proxy trusted frp nginx 代理" },
  { key: "password", label: "修改管理密码", keywords: "password security 密码 安全" },
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

const filteredMenuItems = computed(() => {
  if (!menuSearch.value.trim()) return menuItems;
  return menuItems.filter((item) => {
    const target = `${item.label} ${item.keywords || ""}`;
    return fuzzyIncludes(target, menuSearch.value);
  });
});

let timer = null;

const stopTimer = () => {
  if (!timer) return;
  clearInterval(timer);
  timer = null;
};

const needOverviewRefresh = () => {
  return ["overview", "tasks", "ips"].includes(activeMenuKey.value);
};

const startTimer = () => {
  stopTimer();
  if (!props.active || !auth.token) return;
  timer = setInterval(() => {
    if (needOverviewRefresh()) {
      fetchOverview();
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

const onMenuSelect = async (value) => {
  activeMenuKey.value = value;
  if (value === "proxy") {
    await fetchRealIpConfig();
  } else if (needOverviewRefresh()) {
    await fetchOverview();
  }
};

watch(filteredMenuItems, (items) => {
  if (!items.length) return;
  const hasActive = items.some((item) => item.key === activeMenuKey.value);
  if (!hasActive) {
    activeMenuKey.value = items[0].key;
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
      if (activeMenuKey.value === "proxy") {
        await fetchRealIpConfig();
      } else {
        await fetchOverview();
      }
    }
    startTimer();
  }
);

watch(
  () => auth.token,
  async (token) => {
    if (token && props.active) {
      await fetchOverview();
    }
    startTimer();
  }
);

watch(activeMenuKey, async (nextKey) => {
  if (!auth.token || !props.active) return;
  if (nextKey === "proxy") {
    await fetchRealIpConfig();
    return;
  }
  if (needOverviewRefresh()) {
    await fetchOverview();
  }
});

onMounted(async () => {
  await initAdminAuth();
  if (props.active && auth.token) {
    await fetchOverview();
  }
  startTimer();
});

onUnmounted(() => {
  stopTimer();
});
</script>
