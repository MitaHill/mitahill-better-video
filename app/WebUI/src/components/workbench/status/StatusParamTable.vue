<template>
  <div class="param-table" style="margin-top: 16px;">
    <div class="param-table-title">任务参数</div>
    <table>
      <tbody>
        <tr v-for="row in paramRows" :key="row.label">
          <th>{{ row.label }}</th>
          <td>{{ row.value }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  paramRows: {
    type: Array,
    required: true,
  },
});
</script>
