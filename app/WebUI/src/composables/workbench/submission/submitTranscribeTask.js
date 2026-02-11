import { buildTranscriptionTaskFormData } from "../submitPayloadBuilders";
import { bindSingleTaskAndRefresh, ensureCategory, throwSubmitError } from "./common";

export const submitTranscribeTask = async (ctx) => {
  const {
    enforceCategory,
    transcribeForm,
    parseJsonSafe,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  } = ctx;

  ensureCategory(enforceCategory, "transcribe");
  if (!transcribeForm.mediaFiles || transcribeForm.mediaFiles.length === 0) {
    throw new Error("请至少上传一个要转录的音频或视频文件。");
  }

  const data = buildTranscriptionTaskFormData(transcribeForm);
  const res = await fetch("/api/transcriptions", { method: "POST", body: data });
  if (!res.ok) {
    await throwSubmitError({
      response: res,
      parseJsonSafe,
      taskIds,
      setStatusQuery,
      fallbackMessage: "提交转录任务失败。",
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
