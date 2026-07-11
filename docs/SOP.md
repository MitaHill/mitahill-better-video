# Operational SOP

## Runtime rules

- Use `pre-run/` for normal start, stop, logs, and validation.
- Persistent runtime state must stay under `pre-run/storage/`.
- Do not validate regular deployments with ad-hoc project-root `docker run`
  commands, because they can mount or create the wrong storage path.
- The service listens on host port `8501`; clear port conflicts before restart.

## Engineering standard

- Prefer easy-to-implement, robust, minimal, and simple changes.
- Do not add broad abstractions, multi-path logic, or new schedulers unless the
  current concrete problem cannot be solved safely without them.
- Reuse existing project APIs, services, database helpers, and worker modules
  before introducing new pathways.
- Keep startup and recovery paths especially small: they must fail clearly,
  avoid network dependency, and clean up their own temporary state.
- A change that is clever but harder to operate is not acceptable for this
  project unless explicitly justified in the same commit.

## Process model

- `app/main.py` is the only normal process supervisor.
- Flask serves the API and static frontend.
- The Worker runs as a managed subprocess.
- Frontend code must not start Worker processes.
- On SIGTERM/SIGINT, the main process must terminate the Worker cleanly.

## Initialization rule

Avoid heavyweight work at module import time.

GPU probing, model hash checks, `nvidia-smi`, and similar work must be behind
explicit runtime initialization, not top-level imports. This prevents child
process restart loops and import-time resource contention.

## Startup self-check rule

- Startup self-check is always enabled and intentionally minimal.
- It must first run `nvidia-smi`; if that fails, log the command output and stop
  the process.
- It may run one tiny GPU-backed task through existing project service/worker
  modules, then delete the task row and temporary files.
- It must not run broad multi-module validation or download models from the
  internet.
- Deeper validation belongs in admin debug tools or manual smoke tests after the
  service has started.

## Performance and cleanup

- Production logging defaults to `INFO`; avoid tile/frame-level `DEBUG` logs.
- Model-heavy work must go through the lightweight GPU model coordinator.
  Before loading a model, release other registered models and check free VRAM;
  if VRAM is insufficient, fail clearly instead of loading another model.
- After each task, registered GPU models must be released immediately, then
  Python and CUDA memory should be cleaned with `gc.collect()` and
  `torch.cuda.empty_cache()`.
- Transcription video output must add subtitles as soft subtitle streams and
  copy existing video/audio streams; translated videos contain original,
  translated, and bilingual subtitle tracks, while untranslated videos contain
  only the original subtitle track.
- Subtitle muxing must use a safe temporary subtitle path under
  `/workspace/storage/tmp/subtitles/`, such as `render_subtitle_<hash>.srt`,
  and delete it immediately after ffmpeg exits.
- Transcription uses original OpenAI Whisper only. CUDA is required; do not add
  CPU fallback paths. On old NVIDIA GPUs such as GTX 960 4G, run Whisper with
  `fp16=False`. If `medium` does not fit VRAM on a target machine, fail clearly
  and let the user select a smaller downloaded model.
- Automatic expired-task deletion is currently disabled. Admin users delete
  completed/failed task files and database records explicitly from the task
  overview table.

## Build and deploy

Build image from repository root:

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

Model packaging rule:

- Small, stable model files can be committed when they materially improve
  repeatable builds.
- Large model weights should stay in the Docker base image layer or an explicit
  model volume, not in the source repository.
- Enhancement keeps original audio by default. Audio enhancement models such as
  VoiceFixer and DeepFilterNet are not part of the default image.
- FFmpeg uses the Ubuntu package by default for old NVIDIA driver
  compatibility. A checksum-verified prebuilt FFmpeg archive can be enabled at
  build time, but newer FFmpeg builds may require newer NVIDIA drivers. The app
  exposes only codecs that pass a tiny NVENC encode test on the current GPU.

Deploy from `pre-run/`:

```bash
cd pre-run
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=200 better_video
```

Validation checklist:

1. Container is running and not restarting.
2. `/api/health` returns healthy status.
3. Logs show Worker startup without traceback.
4. Frontend loads from port `8501`.
5. A small task can be submitted, completed, and deleted from admin.

## Git workflow

- Branch roles:
  - `dev`: development branch for new features, fixes, and documentation work.
  - `main`: stable branch for tested versions only.
- Start new work from `dev`. Do not develop directly on `main`.
- Merge `dev` into `main` only after the branch is validated and ready to be
  treated as stable.
- Keep changes scoped and commit with semantic prefixes or short Chinese
  summaries that clearly state the change:
  - `feat:` feature or behavior change
  - `fix:` bug fix
  - `docs:` documentation-only change
  - `perf:` performance change
  - `chore:` maintenance
- Every commit on `dev` must be tested before commit. Use the narrowest useful
  check for the change, then run broader checks before merging to `main`.
- Recommended checks:
  - Python/backend: `python3 -m compileall -q app/src`
  - Frontend: `cd app/WebUI && npm run build`
  - Runtime/config: `cd pre-run && docker compose config`
  - Behavior change: run a small real task and confirm status/output/logs
- Primary remote is `origin`.
- Before pushing, check:

```bash
git status -sb
git log --oneline --decorate -5
```

- Push the current branch explicitly:

```bash
git push -u origin "$(git branch --show-current)"
```
