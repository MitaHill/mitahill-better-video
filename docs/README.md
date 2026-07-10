# MitaHill Better Video

Flask + Vue web UI for video/image processing around Real-ESRGAN. The current
frontend exposes enhancement, conversion, transcription, watermark/download
workflows, and an admin console.

## Main capabilities

- Image/video upscaling with Real-ESRGAN.
- Models: `realesrgan-x4plus`, `realesrnet-x4plus`, `realesr-general-x4v3`.
- Denoise control for `realesr-general-x4v3` through DNI blending.
- Batch image upload with ZIP download.
- Video output with optional original/enhanced audio, CRF, codec, deinterlace,
  tiling, and FP16 controls.
- Admin console for task overview, cancellation/deletion, maintenance mode,
  real IP configuration, GPU usage, logs, and password management.

## Standard runtime

Use `pre-run/` as the runtime entry:

```bash
cd pre-run
docker compose up -d
docker compose ps
docker compose logs --tail=200 better_video
```

Persistent data lives under `pre-run/storage/`:

- `upload/` uploaded source files
- `output/` generated outputs and per-run scratch
- `data/tasks.db` SQLite database
- `logs/` runtime logs
- `models/` runtime model cache

Build from the repository root when needed:

```bash
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

## Configuration

- Runtime env file: `pre-run/.env`, mounted to `/workspace/config/.env`.
- Template: `config/.env.example`.
- Settings loader: `app/src/Config/settings.py`.
- Default port: `8501` with host networking.

## Important paths

- API service: `app/main.py`, `app/src/Api/`
- Worker: `app/src/Worker/`
- Database helpers: `app/src/Database/`
- Frontend: `app/WebUI/`
- Model weights: `app/models/`
- Compose files: `deploy/compose/`
- Dockerfiles: `deploy/docker/`

## Related docs

- [Architecture](ARCHITECTURE.md)
- [API contract](API.md)
- [Operational SOP](SOP.md)
- [Real IP deployment](DEPLOY_REAL_IP.md)
- [Compose workflows](../deploy/compose/README.md)

## Git baseline

- `dev`: daily development branch. New features and fixes start here.
- `main`: stable branch. Merge only tested, release-ready changes from `dev`.
- Every commit on `dev` must be validated before commit; record the relevant
  test command or manual verification in the commit/PR notes.

## Acknowledgements

- Real-ESRGAN by Xintao et al.: https://github.com/xinntao/Real-ESRGAN
