import { buildConvertTaskFormData } from "../submitPayloadBuilders";
import { bindSingleTaskAndRefresh, ensureCategory, throwSubmitError } from "./common";

export const submitConvertTask = async (ctx) => {
  const {
    enforceCategory,
    convertForm,
    parseJsonSafe,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  } = ctx;

  ensureCategory(enforceCategory, "convert");
  if (!convertForm.mediaFiles || convertForm.mediaFiles.length === 0) {
    throw new Error("请至少上传一个音频或视频文件。");
  }

  const data = buildConvertTaskFormData(convertForm);
  const res = await fetch("/api/conversions", { method: "POST", body: data });
  if (!res.ok) {
    await throwSubmitError({
      response: res,
      parseJsonSafe,
      taskIds,
      setStatusQuery,
      fallbackMessage: "提交转换任务失败。",
    });
  }

  const payload = await parseJsonSafe(res);
  await bindSingleTaskAndRefresh({
    taskId: payload.task_id,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  });
};
