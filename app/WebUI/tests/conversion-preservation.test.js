import { test } from "node:test";
import assert from "node:assert/strict";
import { useWorkbenchFormsState } from "../src/composables/workbench/useWorkbenchFormsState.js";
import { useWorkbenchUploads } from "../src/composables/workbench/useWorkbenchUploads.js";
import { buildConvertTaskFormData } from "../src/composables/workbench/submitPayloadBuilders/convertPayloadBuilder.js";

test("conversion defaults leave media properties unchanged", () => {
  const { convertForm } = useWorkbenchFormsState();
  assert.equal(convertForm.outputFormat, "preserve");
  assert.equal(convertForm.videoCodec, "preserve");
  for (const key of ["frameRate", "crf", "videoBitrateK", "targetWidth", "targetHeight"]) {
    assert.equal(convertForm[key], 0);
  }
});

test("probing multiple files does not turn source information into edits", async () => {
  const state = useWorkbenchFormsState();
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ has_video: true, width: 1920, height: 1080, fps: 29.97, video_bitrate: 8000000, video_codec: "h264" }) });
  try {
    const uploads = useWorkbenchUploads({ ...state, submitError: { value: "" }, submitWarnings: { value: "" }, parseJsonSafe: (res) => res.json() });
    await uploads.onConvertMediaChange({ target: { files: [{ name: "one.mp4" }, { name: "two.mp4" }], value: "chosen" } });
    assert.equal(state.convertMediaInfo.value.length, 2);
    assert.equal(state.convertForm.frameRate, 0);
    assert.equal(state.convertForm.targetWidth, 0);
    assert.equal(state.convertForm.videoBitrateK, 0);
    assert.equal(state.convertForm.videoCodec, "preserve");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("upload carries the source file mtime separately from media metadata", () => {
  const { convertForm } = useWorkbenchFormsState();
  const file = new File(["fixture"], "source.mp4", { lastModified: 1577934245000 });
  convertForm.mediaFiles = [file];
  const data = buildConvertTaskFormData(convertForm);
  assert.deepEqual(JSON.parse(data.get("source_file_times")), [{ filename: "source.mp4", last_modified_ms: 1577934245000 }]);
  assert.equal(data.get("video_codec"), "preserve");
});
