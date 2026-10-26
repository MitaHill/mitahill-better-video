import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));

const readGit = (...args) => {
  try {
    return execFileSync("git", args, { cwd: rootDir, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
};

// 镜像构建没有 .git，由 CI 传入；本地开发直接读取当前工作区。
const buildChannel = process.env.BUILD_CHANNEL || (readGit("branch", "--show-current") === "main" ? "stable" : "dev");
const gitSha = process.env.GIT_SHA || readGit("rev-parse", "HEAD");
const buildInfo = {
  channel: buildChannel === "stable" ? "稳定版" : "开发版",
  gitHash: /^[a-f0-9]{7,40}$/i.test(gitSha) ? gitSha.slice(0, 7) : "未知提交",
};

const copyFfmpegCore = () => ({
  name: "copy-ffmpeg-core",
  closeBundle() {
    const targetDir = resolve(rootDir, "dist/ffmpeg");
    mkdirSync(targetDir, { recursive: true });
    for (const filename of ["ffmpeg-core.js", "ffmpeg-core.wasm"]) {
      copyFileSync(
        resolve(rootDir, "node_modules/@ffmpeg/core/dist/esm", filename),
        resolve(targetDir, filename)
      );
    }
  },
});

export default defineConfig({
  define: {
    __BUILD_INFO__: JSON.stringify(buildInfo),
  },
  plugins: [vue(), copyFfmpegCore()],
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
