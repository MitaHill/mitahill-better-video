import { reactive, ref } from "vue";

import { CATEGORY_FIELD_MAP } from "../../constants/formConstraints";

const DEFAULT_CONSTRAINTS = Object.freeze({ version: 1, categories: {} });

const toBool = (value, fallback = false) => {
  if (value === undefined || value === null) return fallback;
  if (typeof value === "boolean") return value;
  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
};

const toNumber = (value, numberType, fallback = 0) => {
  if (numberType === "int") {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) return parsed;
    const fb = Number.parseInt(fallback, 10);
    return Number.isFinite(fb) ? fb : 0;
  }
  const parsed = Number.parseFloat(value);
  if (Number.isFinite(parsed)) return parsed;
  const fb = Number.parseFloat(fallback);
  return Number.isFinite(fb) ? fb : 0;
};

const pickAllowed = (value, allowedValues = []) => {
  const target = String(value ?? "").trim().toLowerCase();
  if (!target) return null;
  for (const item of allowedValues) {
    if (target === String(item ?? "").trim().toLowerCase()) return item;
  }
  return null;
};

export const useWorkbenchFormConstraints = ({ parseJsonSafe, enhanceForm, convertForm, transcribeForm }) => {
  const constraints = ref(DEFAULT_CONSTRAINTS);
  const status = reactive({
    loading: false,
    error: "",
    ready: false,
  });

  const categoryForms = {
    enhance: enhanceForm,
    convert: convertForm,
    transcribe: transcribeForm,
  };

  const _categoryConfig = (category) => {
    const payload = constraints.value || DEFAULT_CONSTRAINTS;
    return payload?.categories?.[category] || null;
  };

  const getFieldPolicy = (category, formFieldKey) => {
    const categoryConfig = _categoryConfig(category);
    const apiFieldKey = CATEGORY_FIELD_MAP?.[category]?.[formFieldKey];
    if (!categoryConfig || !apiFieldKey) return null;

    const rawField = categoryConfig?.fields?.[apiFieldKey];
    if (!rawField) return null;

    const globalLock = String(categoryConfig.global_lock || "free").toLowerCase();
    const lock = String(rawField.lock || "free").toLowerCase();
    const effectiveLock = globalLock === "fixed" ? "fixed" : lock;

    return {
      apiFieldKey,
      label: rawField.label || apiFieldKey,
      kind: rawField.kind || "string",
      lock,
      globalLock,
      effectiveLock,
      disabled: effectiveLock === "fixed",
      defaultValue: rawField.default_value,
      fixedValue: rawField.fixed_value,
      minValue: rawField.min_value,
      maxValue: rawField.max_value,
      step: rawField.step,
      numberType: rawField.number_type || "float",
      allowedValues: Array.isArray(rawField.allowed_values) ? rawField.allowed_values : [],
      sensitive: Boolean(rawField.sensitive),
    };
  };

  const sanitizeValueByPolicy = (value, policy) => {
    if (!policy) return value;

    if (policy.effectiveLock === "fixed") {
      return policy.fixedValue;
    }

    if (policy.kind === "boolean") {
      let next = toBool(value, toBool(policy.defaultValue, false));
      if (policy.allowedValues.length && !policy.allowedValues.includes(next)) {
        next = toBool(policy.defaultValue, false);
      }
      return next;
    }

    if (policy.kind === "number") {
      let next = toNumber(value, policy.numberType, policy.defaultValue);
      if (policy.effectiveLock === "range") {
        if (Number.isFinite(Number(policy.minValue))) next = Math.max(Number(policy.minValue), next);
        if (Number.isFinite(Number(policy.maxValue))) next = Math.min(Number(policy.maxValue), next);
      }
      if (policy.allowedValues.length && !policy.allowedValues.includes(next)) {
        next = toNumber(policy.defaultValue, policy.numberType, 0);
      }
      return policy.numberType === "int" ? Number.parseInt(next, 10) : Number(next);
    }

    const text = String(value ?? policy.defaultValue ?? "");
    if (!policy.allowedValues.length) return text;
    const picked = pickAllowed(text, policy.allowedValues);
    if (picked !== null) return picked;
    return pickAllowed(policy.defaultValue, policy.allowedValues) ?? policy.allowedValues[0];
  };

  const enforceCategory = (category) => {
    const form = categoryForms[category];
    if (!form) return;
    const fieldMap = CATEGORY_FIELD_MAP?.[category] || {};
    Object.keys(fieldMap).forEach((formKey) => {
      if (!Object.prototype.hasOwnProperty.call(form, formKey)) return;
      const policy = getFieldPolicy(category, formKey);
      if (!policy) return;
      form[formKey] = sanitizeValueByPolicy(form[formKey], policy);
    });
  };

  const enforceAll = () => {
    enforceCategory("enhance");
    enforceCategory("convert");
    enforceCategory("transcribe");
  };

  const fetchConstraints = async () => {
    status.loading = true;
    status.error = "";
    try {
      const res = await fetch("/api/form-constraints");
      const payload = await parseJsonSafe(res);
      if (!res.ok) {
        throw new Error(payload.error || "读取参数约束失败");
      }
      constraints.value = payload || DEFAULT_CONSTRAINTS;
      enforceAll();
    } catch (error) {
      status.error = error.message;
      constraints.value = DEFAULT_CONSTRAINTS;
    } finally {
      status.loading = false;
      status.ready = true;
    }
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
