import { reactive, ref } from "vue";

const DEFAULT_CONSTRAINTS = Object.freeze({ version: 1, categories: {} });

export const useWorkbenchFormConstraints = () => {
  const constraints = ref(DEFAULT_CONSTRAINTS);
  const status = reactive({
    loading: false,
    error: "",
    ready: false,
  });

  const getFieldPolicy = () => null;
  const enforceCategory = () => {};
  const enforceAll = () => {};

  const fetchConstraints = async () => {
    constraints.value = DEFAULT_CONSTRAINTS;
    status.loading = false;
    status.error = "";
    status.ready = true;
  };

  return {
    constraints,
    status,
    fetchConstraints,
    getFieldPolicy,
    enforceCategory,
    enforceAll,
  };
};
