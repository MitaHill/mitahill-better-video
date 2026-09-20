export const menuTree = Object.freeze([
  {
    key: "runtime",
    label: "运行监控",
    keywords: "runtime monitor task ip gpu log 监控 任务 统计",
    children: Object.freeze([
      {
        key: "runtime_tasks",
        label: "任务与状态",
        keywords: "overview task queue status maintenance 任务 总览 状态 维护",
        children: Object.freeze([
          { key: "overview", label: "任务总览", keywords: "overview summary 任务 总览" },
          { key: "tasks", label: "任务状态浏览", keywords: "task queue processing 任务 状态" },
        ]),
      },
      {
        key: "runtime_access",
        label: "访问与日志",
        keywords: "logs warning error 日志",
        children: Object.freeze([
          { key: "logs_warn", label: "系统日志", keywords: "log warn error warning 系统 日志" },
        ]),
      },
      {
        key: "runtime_transcribe",
        label: "转录中心",
        keywords: "transcribe transcription subtitle whisper model translate 转录 字幕 模型 翻译",
        children: Object.freeze([
          { key: "transcribe_cfg_elevenlabs", label: "ElevenLabs Scribe", keywords: "elevenlabs scribe api cloud 云端 转录" },
          { key: "transcribe_cfg_translation", label: "翻译源设置", keywords: "translate provider openai 翻译 源" },
          { key: "transcribe_cfg_catalog", label: "转录模型目录", keywords: "catalog download model transcription 模型 目录 下载" },
          { key: "debug_tests", label: "测试", keywords: "debug test transcription whisper translate provider 调试 测试 转录 翻译" },
        ]),
      },
    ]),
  },
  {
    key: "system",
    label: "系统设置",
    keywords: "security password 安全 密码",
    children: Object.freeze([
      {
        key: "security",
        label: "安全",
        keywords: "password security 密码 安全",
        children: Object.freeze([
          { key: "password", label: "修改管理密码", keywords: "password security 密码 安全" },
        ]),
      },
    ]),
  },
]);

const fuzzyIncludes = (text, query) => {
  const source = String(text || "").toLowerCase();
  const target = String(query || "").toLowerCase().trim();
  if (!target) return true;
  if (source.includes(target)) return true;
  let i = 0;
  for (const ch of source) {
    if (ch === target[i]) i += 1;
    if (i >= target.length) return true;
  }
  return false;
};

const filterTreeNode = (node, query) => {
  const current = `${node.label || ""} ${node.keywords || ""}`;
  const selfMatched = fuzzyIncludes(current, query);
  const children = Array.isArray(node.children) ? node.children : [];
  if (!children.length) return selfMatched ? { ...node } : null;
  if (selfMatched) return { ...node };
  const filteredChildren = children
    .map((child) => filterTreeNode(child, query))
    .filter(Boolean);
  if (!filteredChildren.length) return null;
  return { ...node, children: filteredChildren };
};

export const filterMenuTree = (query) => {
  const safeQuery = String(query || "").trim();
  if (!safeQuery) return menuTree;
  return menuTree.map((node) => filterTreeNode(node, safeQuery)).filter(Boolean);
};
