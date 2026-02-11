export const ensureCategory = (enforceCategory, category) => {
  if (typeof enforceCategory === "function") {
    enforceCategory(category);
  }
};

export const setTaskFromErrorPayload = (taskIds, setStatusQuery, payload) => {
  const taskId = payload && payload.task_id ? String(payload.task_id) : "";
  if (!taskId) return;
  taskIds.value = [taskId];
  setStatusQuery(taskId);
};

export const throwSubmitError = async ({
  response,
  parseJsonSafe,
  taskIds,
  setStatusQuery,
  fallbackMessage,
}) => {
  const payload = await parseJsonSafe(response);
  setTaskFromErrorPayload(taskIds, setStatusQuery, payload);
  throw new Error((payload && payload.error) || fallbackMessage);
};

export const bindSingleTaskAndRefresh = async ({
  taskId,
  taskIds,
  setStatusQuery,
  joinRoom,
  fetchStatus,
}) => {
  const safeTaskId = String(taskId || "").trim();
  if (!safeTaskId) return;
  taskIds.value = [safeTaskId];
  setStatusQuery(safeTaskId);
  joinRoom();
  await fetchStatus();
};

export const bindBatchTasksAndRefresh = async ({
  taskIdList,
  warnings,
  taskIds,
  submitWarnings,
  setStatusQuery,
  joinRoom,
  fetchStatus,
}) => {
  const safeIds = Array.isArray(taskIdList) ? taskIdList.filter(Boolean) : [];
  taskIds.value = safeIds;
  if (Array.isArray(warnings) && warnings.length) {
    submitWarnings.value = warnings.map((item) => `${item.filename}: ${item.error}`).join("；");
  }
  if (!safeIds.length) return;
  setStatusQuery(safeIds[0]);
  joinRoom();
  await fetchStatus();
};
