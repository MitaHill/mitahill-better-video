export const useFieldPolicy = (getFieldPolicy, category) => {
  const readPolicy = (fieldKey) => getFieldPolicy(category, fieldKey) || null;
  const isDisabled = (fieldKey) => Boolean(readPolicy(fieldKey)?.disabled);
  const allowed = (fieldKey, fallback = []) => {
    const values = readPolicy(fieldKey)?.allowedValues;
    return Array.isArray(values) && values.length ? values : fallback;
  };
  const toFiniteOr = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  const numMin = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.minValue, fallback);
  const numMax = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.maxValue, fallback);
  const numStep = (fieldKey, fallback) => toFiniteOr(readPolicy(fieldKey)?.step, fallback);

  return { readPolicy, isDisabled, allowed, numMin, numMax, numStep };
};
