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
      <div class="panel admin-card">
        <div class="status-row admin-head-row">
          <h2>后端管理</h2>
          <div class="status-row" style="gap: 8px;">
            <span class="notice">会话有效期：{{ auth.expiresAt || '-' }}</span>
            <button class="secondary" @click="logoutAdmin">退出登录</button>
          </div>
        </div>

        <AdminOverviewCards :counts="overview.counts" />

        <p class="notice" v-if="overview.realIpConfig" style="margin-top: 10px;">
          当前请求识别IP：{{ overview.realIpConfig.resolved_client_ip }} ｜ 受信代理：{{ overview.realIpConfig.trusted_proxies }}
        </p>
      </div>

      <AdminTaskTable
        :tasks="overview.tasks"
        :status-filter="overview.statusFilter"
        :loading="overview.loading"
        :error="overview.error"
        :on-refresh="fetchOverview"
        @update:status-filter="onStatusFilterChange"
      />

      <AdminIpTable :ip-stats="overview.ipStats" />

      <AdminPasswordForm
        :old-password="passwordForm.oldPassword"
        :new-password="passwordForm.newPassword"
        :loading="passwordForm.loading"
        :error="passwordForm.error"
        :message="passwordForm.message"
        :on-change-password="changeAdminPassword"
        @update:old-password="onOldPasswordInput"
        @update:new-password="onNewPasswordInput"
      />
    </template>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from "vue";

import { useWorkbenchAdmin } from "../../composables/workbench/useWorkbenchAdmin";
import { parseJsonSafe } from "../../composables/workbench/utils";
import AdminIpTable from "./AdminIpTable.vue";
import AdminLoginCard from "./AdminLoginCard.vue";
import AdminOverviewCards from "./AdminOverviewCards.vue";
import AdminPasswordForm from "./AdminPasswordForm.vue";
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
  initAdminAuth,
  loginAdmin,
  logoutAdmin,
  fetchOverview,
  changeAdminPassword,
} = useWorkbenchAdmin({ parseJsonSafe });

let timer = null;

const stopTimer = () => {
  if (!timer) return;
  clearInterval(timer);
  timer = null;
};

const startTimer = () => {
  stopTimer();
  if (!props.active || !auth.token) return;
  timer = setInterval(() => {
    fetchOverview();
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

const onStatusFilterChange = (value) => {
  overview.statusFilter = value;
  fetchOverview();
};

watch(
  () => props.active,
  async (isActive) => {
    if (!isActive) {
      stopTimer();
      return;
    }
    if (auth.token) {
      await fetchOverview();
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
