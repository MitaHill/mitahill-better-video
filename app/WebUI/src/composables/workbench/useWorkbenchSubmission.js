import { buildConvertTaskFormData, buildEnhanceTaskFormData, buildTranscriptionTaskFormData } from "./submitPayloadBuilders";

export const useWorkbenchSubmission = ({
  activeCategory,
  loading,
  submitError,
  submitWarnings,
  enhanceForm,
  convertForm,
  transcribeForm,
  downloadForm,
  taskIds,
  setStatusQuery,
  fetchStatus,
  joinRoom,
  parseJsonSafe,
  enforceCategory,
}) => {
  const submitEnhanceTask = async () => {
    if (typeof enforceCategory === "function") {
      enforceCategory("enhance");
    }
    if (!enhanceForm.files || enhanceForm.files.length === 0) {
      throw new Error("请先选择要上传的文件。");
    }

    const endpoint = enhanceForm.files.length > 1 ? "/api/tasks/batch" : "/api/tasks";
    const data = buildEnhanceTaskFormData(enhanceForm);
    const res = await fetch(endpoint, { method: "POST", body: data });

    if (!res.ok) {
      const err = await parseJsonSafe(res);
      if (err.task_id) {
        taskIds.value = [err.task_id];
        setStatusQuery(err.task_id);
      }
      throw new Error(err.error || "提交失败，请稍后重试。");
    }

    const payload = await parseJsonSafe(res);
    if (endpoint.endsWith("/batch")) {
      taskIds.value = payload.task_ids || [];
      if (payload.errors && payload.errors.length) {
        submitWarnings.value = payload.errors.map((e) => `${e.filename}: ${e.error}`).join("；");
      }
      if (taskIds.value.length) {
        setStatusQuery(taskIds.value[0]);
        joinRoom();
        await fetchStatus();
      }
      return;
    }

    taskIds.value = [payload.task_id];
    setStatusQuery(payload.task_id);
    joinRoom();
    await fetchStatus();
  };

  const submitConvertTask = async () => {
    if (typeof enforceCategory === "function") {
      enforceCategory("convert");
    }
    if (!convertForm.mediaFiles || convertForm.mediaFiles.length === 0) {
      throw new Error("请至少上传一个音频或视频文件。");
    }

    const data = buildConvertTaskFormData(convertForm);
    const res = await fetch("/api/conversions", { method: "POST", body: data });

    if (!res.ok) {
      const err = await parseJsonSafe(res);
      if (err.task_id) {
        taskIds.value = [err.task_id];
        setStatusQuery(err.task_id);
      }
      throw new Error(err.error || "提交转换任务失败。");
    }

    const payload = await parseJsonSafe(res);
    taskIds.value = [payload.task_id];
    setStatusQuery(payload.task_id);
    joinRoom();
    await fetchStatus();
  };

  const submitTranscribeTask = async () => {
    if (typeof enforceCategory === "function") {
      enforceCategory("transcribe");
    }
    if (!transcribeForm.mediaFiles || transcribeForm.mediaFiles.length === 0) {
      throw new Error("请至少上传一个要转录的音频或视频文件。");
    }
    if (
      String(transcribeForm.translateTo || "").trim() &&
      String(transcribeForm.translatorProvider || "none").trim().toLowerCase() === "none"
    ) {
      throw new Error("已设置“翻译到”，请先选择翻译提供器，或将“翻译到”改为“不翻译”。");
    }

    const data = buildTranscriptionTaskFormData(transcribeForm);
    const res = await fetch("/api/transcriptions", { method: "POST", body: data });

    if (!res.ok) {
      const err = await parseJsonSafe(res);
      if (err.task_id) {
        taskIds.value = [err.task_id];
        setStatusQuery(err.task_id);
      }
      throw new Error(err.error || "提交转录任务失败。");
    }

    const payload = await parseJsonSafe(res);
    taskIds.value = [payload.task_id];
    setStatusQuery(payload.task_id);
    joinRoom();
    await fetchStatus();
  };

  const submitDownloadTask = async () => {
    const rawUrl = String(downloadForm.url || "").trim();
    if (!rawUrl) {
      throw new Error("请先输入要下载的视频链接。");
    }
    const data = new FormData();
    data.append("url", rawUrl);
    data.append("output_format", String(downloadForm.outputFormat || "mp4"));
    data.append("audio_only", String(Boolean(downloadForm.audioOnly)));

    const res = await fetch("/api/downloads/direct", { method: "POST", body: data });
    const payload = await parseJsonSafe(res);
    if (!res.ok) {
      throw new Error(payload.error || "下载任务失败。");
    }

    taskIds.value = [];
    setStatusQuery("");
    const files = Array.isArray(payload.files) ? payload.files : [];
    if (files.length) {
      submitWarnings.value = `下载完成，输出目录：${payload.output_dir}，文件：${files.map((f) => f.name).join("，")}`;
    } else {
      submitWarnings.value = `下载完成，输出目录：${payload.output_dir}`;
    }
  };

  const submitTask = async () => {
    submitError.value = "";
    submitWarnings.value = "";
    loading.submit = true;
    try {
      if (activeCategory.value === "download") {
        await submitDownloadTask();
      } else if (activeCategory.value === "convert") {
        await submitConvertTask();
      } else if (activeCategory.value === "transcribe") {
        await submitTranscribeTask();
      } else {
        await submitEnhanceTask();
      }
    } catch (error) {
      submitError.value = error.message;
    } finally {
      loading.submit = false;
    }
  };

  return {
    submitTask,
  };
};
