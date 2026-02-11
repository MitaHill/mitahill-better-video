const DIRECT_TS_RE = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/;

export const formatDateTimeToSecond = (value, fallback = "-") => {
  if (value === null || value === undefined) return fallback;
  const raw = String(value).trim();
  if (!raw) return fallback;

  const directMatch = raw.match(DIRECT_TS_RE);
  if (directMatch) {
    return `${directMatch[1]} ${directMatch[2]}`;
  }

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  const sec = String(date.getSeconds()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}:${sec}`;
};
