export const isFilenameSafe = (name) => {
  if (!name || name.length > 180) return false;
  if (name.includes("/") || name.includes("\\")) return false;
  return !/[\u0000-\u001f\u007f]/.test(name);
};

export const validateFiles = (files) => files.every((f) => isFilenameSafe(f.name));

export const parseJsonSafe = async (res) => {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return res.json();
  const text = await res.text();
  throw new Error(text || "服务返回非JSON响应。");
};

export const formatBool = (value) => (value ? "是" : "否");
