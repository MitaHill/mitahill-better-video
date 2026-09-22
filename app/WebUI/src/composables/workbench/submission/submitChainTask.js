import { bindBatchTasksAndRefresh, throwSubmitError } from "./common";

export const submitChainTask = async (ctx) => {
  const {
    chain,
    parseJsonSafe,
    taskIds,
    setStatusQuery,
    submitWarnings,
    joinRoom,
    fetchStatus,
  } = ctx;

  if (!chain) {
    throw new Error("链式任务未初始化。");
  }
  const invalid = chain.validateChain();
  if (invalid) {
    throw new Error(invalid);
  }

  const payload = chain.buildChainPayload();
  const data = new FormData();
  data.append("file", payload.file);
  data.append("steps", JSON.stringify(payload.steps));

  const res = await fetch("/api/chains", { method: "POST", body: data });
  if (!res.ok) {
    await throwSubmitError({
      response: res,
      parseJsonSafe,
      taskIds,
      setStatusQuery,
      fallbackMessage: "提交失败，请稍后重试。",
    });
  }

  const body = await parseJsonSafe(res);
  // 链就是一个批次，状态面板按批次 ID 跟踪
  await bindBatchTasksAndRefresh({
    batchId: body.chain_id,
    taskIdList: body.task_ids || [],
    warnings: [],
    taskIds,
    submitWarnings,
    setStatusQuery,
    joinRoom,
    fetchStatus,
  });
};
