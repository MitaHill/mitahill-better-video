import { buildDownloadTaskFormData } from "../submitPayloadBuilders";
import { bindSingleTaskAndRefresh, ensureCategory } from "./common";

export const submitDownloadTask = async (ctx) => {
  const {
    enforceCategory,
    downloadForm,
    parseJsonSafe,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  } = ctx;

  ensureCategory(enforceCategory, "download");
  const rawUrl = String(downloadForm.sourceUrl || "").trim();
  if (!rawUrl) {
    throw new Error("请先输入要下载的视频链接。");
  }
  if (!downloadForm.probeReady) {
    throw new Error("请先点击“解析清晰度与字幕”。");
  }
  if (downloadForm.downloadMode === "subtitle_only" && (!downloadForm.subtitleLanguages || !downloadForm.subtitleLanguages.length)) {
    throw new Error("仅字幕模式请至少选择一种字幕语言。");
  }

  const data = buildDownloadTaskFormData(downloadForm);
  const res = await fetch("/api/downloads/tasks", { method: "POST", body: data });
  const payload = await parseJsonSafe(res);
  if (!res.ok) {
    throw new Error(payload.error || "下载任务失败。");
  }

  await bindSingleTaskAndRefresh({
    taskId: payload.task_id,
    taskIds,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  });
};
