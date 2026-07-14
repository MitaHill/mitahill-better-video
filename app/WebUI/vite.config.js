import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));

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
  plugins: [vue(), copyFfmpegCore()],
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
