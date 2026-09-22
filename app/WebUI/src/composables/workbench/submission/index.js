import { submitChainTask } from "./submitChainTask";
import { submitConvertTask } from "./submitConvertTask";
import { submitEnhanceTask } from "./submitEnhanceTask";
import { submitTranscribeTask } from "./submitTranscribeTask";

const submitterMap = Object.freeze({
  chain: submitChainTask,
  convert: submitConvertTask,
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
  submitConvertTask,
  submitTranscribeTask,
};
