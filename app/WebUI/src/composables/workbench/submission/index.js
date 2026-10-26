import { submitChainTask } from "./submitChainTask";
import { submitEnhanceTask } from "./submitEnhanceTask";
import { submitTranscribeTask } from "./submitTranscribeTask";

const submitterMap = Object.freeze({
  chain: submitChainTask,
  transcribe: submitTranscribeTask,
  enhance: submitEnhanceTask,
});

export const resolveSubmitter = (activeCategory) => {
  const safe = String(activeCategory || "enhance").trim().toLowerCase();
  return submitterMap[safe] || submitterMap.enhance;
};

export {
  submitChainTask,
  submitEnhanceTask,
  submitTranscribeTask,
};
