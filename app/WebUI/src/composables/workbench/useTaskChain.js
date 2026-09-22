import { reactive, ref } from "vue";
import { useWorkbenchFormsState } from "./useWorkbenchFormsState";
import {
  buildConvertTaskFormData,
  buildEnhanceTaskFormData,
  buildTranscriptionTaskFormData,
} from "./submitPayloadBuilders";

export const CHAIN_MAX_STEPS = 5;

export const CHAIN_CATEGORY_OPTIONS = Object.freeze([
  { value: "enhance", label: "增强" },
  { value: "convert", label: "转换" },
  { value: "transcribe", label: "转录" },
]);

// 每一步的参数映射跟单任务完全一样，直接复用现有构建器，再把文件字段摘掉：
// 链的输入只有最前面那一个文件，后续步骤的输入由后端填。
const FILE_KEYS = new Set(["file", "files", "media_files", "watermark_images"]);

const formDataToParams = (formData) => {
  const params = {};
  formData.forEach((value, key) => {
    if (FILE_KEYS.has(key)) return;
    if (typeof File !== "undefined" && value instanceof File) return;
    params[key] = value;
  });
  return params;
};

const buildStepParams = (step) => {
  if (step.category === "convert") return formDataToParams(buildConvertTaskFormData(step.state.convertForm));
  if (step.category === "transcribe") {
    return formDataToParams(buildTranscriptionTaskFormData(step.state.transcribeForm, []));
  }
  return formDataToParams(buildEnhanceTaskFormData(step.state.enhanceForm));
};

let stepSeq = 0;

export const useTaskChain = ({ transcriptionRuntimeConfig }) => {
  const chainFiles = reactive([]);
  const steps = reactive([]);
  const dragIndex = ref(-1);

  const syncTranscribeModel = (step) => {
    if (step.category !== "transcribe") return;
    const config = transcriptionRuntimeConfig?.value?.transcription;
    const installed = Array.isArray(config?.installed_models)
      ? config.installed_models.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean)
      : [];
    if (!installed.length) return;
    const active = String(config?.active_model || "").trim().toLowerCase();
    step.state.transcribeForm.whisperModel = installed.includes(active) ? active : installed[0];
  };

  const createStep = (category) => {
    stepSeq += 1;
    const step = reactive({
      id: `chain_step_${stepSeq}`,
      category,
      state: useWorkbenchFormsState(),
    });
    syncTranscribeModel(step);
    return step;
  };

  const addStep = (category = "enhance") => {
    if (steps.length >= CHAIN_MAX_STEPS) return;
    steps.push(createStep(category));
  };

  const removeStep = (index) => {
    if (index < 0 || index >= steps.length) return;
    steps.splice(index, 1);
  };

  const setStepCategory = (index, category) => {
    const step = steps[index];
    if (!step || step.category === category) return;
    step.category = category;
    syncTranscribeModel(step);
  };

  const moveStep = (from, to) => {
    if (from === to || from < 0 || to < 0 || from >= steps.length || to >= steps.length) return;
    const [moved] = steps.splice(from, 1);
    steps.splice(to, 0, moved);
  };

  const onChainFileChange = (event) => {
    const files = Array.from(event?.target?.files || []);
    chainFiles.splice(0, chainFiles.length, ...files.slice(0, 1));
  };

  const onDragStart = (index) => {
    dragIndex.value = index;
  };

  const onDragOver = (event) => {
    event.preventDefault();
  };

  const onDrop = (index) => {
    moveStep(dragIndex.value, index);
    dragIndex.value = -1;
  };

  // 跟后端 chain_tasks._validate_steps 同一套规则，先在本地挡掉，少一次无谓往返
  const validateChain = () => {
    if (!chainFiles.length) return "请先选择输入文件。";
    if (!steps.length) return "请至少添加一个步骤。";
    if (steps.length > CHAIN_MAX_STEPS) return `一条链最多 ${CHAIN_MAX_STEPS} 步。`;
    const lastIndex = steps.length - 1;
    for (let index = 0; index < steps.length; index += 1) {
      const step = steps[index];
      if (index === lastIndex) continue;
      if (step.category === "transcribe") return "转录产出的是字幕，只能放在链的最后一步。";
      if (step.category === "convert" && step.state.convertForm.convertMode !== "transcode") {
        return `第 ${index + 1} 步的转换类型会产出多个文件，只能放在最后一步。`;
      }
    }
    return "";
  };

  const buildChainPayload = () => ({
    file: chainFiles[0],
    steps: steps.map((step) => ({ category: step.category, params: buildStepParams(step) })),
  });

  return {
    chainFiles,
    chainSteps: steps,
    addStep,
    removeStep,
    setStepCategory,
    moveStep,
    onChainFileChange,
    onDragStart,
    onDragOver,
    onDrop,
    validateChain,
    buildChainPayload,
  };
};
