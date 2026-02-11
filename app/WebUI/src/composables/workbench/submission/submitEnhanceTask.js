import { buildEnhanceTaskFormData } from "../submitPayloadBuilders";
import {
  bindBatchTasksAndRefresh,
  bindSingleTaskAndRefresh,
  ensureCategory,
  throwSubmitError,
} from "./common";

export const submitEnhanceTask = async (ctx) => {
  const {
    enforceCategory,
    enhanceForm,
    parseJsonSafe,
    taskIds,
    setStatusQuery,
    submitWarnings,
    joinRoom,
    fetchStatus,
  } = ctx;

  ensureCategory(enforceCategory, "enhance");
  if (!enhanceForm.files || enhanceForm.files.length === 0) {
    throw new Error("请先选择要上传的文件。");
  }

  const endpoint = enhanceForm.files.length > 1 ? "/api/tasks/batch" : "/api/tasks";
  const data = buildEnhanceTaskFormData(enhanceForm);
  const res = await fetch(endpoint, { method: "POST", body: data });
  if (!res.ok) {
    await throwSubmitError({
      response: res,
      parseJsonSafe,
      taskIds,
      setStatusQuery,
      fallbackMessage: "提交失败，请稍后重试。",
    });
  }

  const payload = await parseJsonSafe(res);
  if (endpoint.endsWith("/batch")) {
    await bindBatchTasksAndRefresh({
      taskIdList: payload.task_ids || [],
      warnings: payload.errors || [],
      taskIds,
      submitWarnings,
      setStatusQuery,
      joinRoom,
      fetchStatus,
    });
    return;
  }

  await bindSingleTaskAndRefresh({
    taskId: payload.task_id,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  });
};
