<template>
  <div class="panel admin-card">
    <h2>访问IP统计（IPv4/IPv6）</h2>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>IP</th>
            <th>版本</th>
            <th>类型</th>
            <th>总访问</th>
            <th>排队</th>
            <th>处理中</th>
            <th>已完成</th>
            <th>失败</th>
            <th>最后活跃</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in ipStats" :key="item.client_ip">
            <td class="mono">{{ item.client_ip || "unknown" }}</td>
            <td>{{ item.ip_info?.version || 0 }}</td>
            <td>{{ scopeText(item.ip_info?.scope) }}</td>
            <td>{{ item.visit_count || 0 }}</td>
            <td>{{ item.pending_count || 0 }}</td>
            <td>{{ item.processing_count || 0 }}</td>
            <td>{{ item.completed_count || 0 }}</td>
            <td>{{ item.failed_count || 0 }}</td>
            <td>{{ item.last_seen || "-" }}</td>
          </tr>
          <tr v-if="!ipStats.length">
            <td colspan="9" class="notice">暂无IP数据</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  ipStats: {
    type: Array,
    required: true,
  },
});

const scopeText = (scope) => {
  const map = {
    public: "公网",
    lan: "局域网",
    loopback: "本机",
    multicast: "组播",
    reserved: "保留",
    invalid: "无效",
    other: "其它",
  };
  return map[scope] || scope || "-";
};
</script>
