# Operational SOP

## Runtime rules

- Use `pre-run/` for normal start, stop, logs, and validation.
- Persistent runtime state must stay under `pre-run/storage/`.
- Do not validate regular deployments with ad-hoc project-root `docker run`
  commands, because they can mount or create the wrong storage path.
- The service listens on host port `8501`; clear port conflicts before restart.

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

## Performance and cleanup

- Production logging defaults to `INFO`; avoid tile/frame-level `DEBUG` logs.
- After model-heavy work, release Python and CUDA memory with `gc.collect()` and
  `torch.cuda.empty_cache()` where the pipeline owns the model lifecycle.
- Automatic expired-task deletion is currently disabled. Admin users delete
  completed/failed task files and database records explicitly from the task
  overview table.

## Build and deploy

Build image from repository root:

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

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

- Keep changes scoped and commit with semantic prefixes:
  - `feat:` feature or behavior change
  - `fix:` bug fix
  - `docs:` documentation-only change
  - `perf:` performance change
  - `chore:` maintenance
- Work on feature branches, then merge into `main` after validation.
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
