# Docker Compose workflows

Run all commands from the repository root unless the command explicitly changes
directory.

## Build images

```bash
docker compose -f deploy/compose/docker-compose.build.yml build base_image
docker compose -f deploy/compose/docker-compose.build.yml build app_image
```

The app image is tagged as `better_video:latest`. The base image is tagged as
`base_better_video:20260210-2330`, matching `deploy/docker/for-app/Dockerfile`.

## Deploy

```bash
cd pre-run
docker compose up -d
docker compose ps
docker compose logs --tail=200 better_video
```

The deploy compose file uses host networking and stores persistent data in
`pre-run/storage/`.

## Development

```bash
docker compose -f deploy/compose/docker-compose.dev.yml up --build
```

This also uses host networking and bind-mounts the repository to `/workspace`.

## Test

```bash
docker compose -f deploy/compose/docker-compose.test.yml run --rm better_video_test
```

The current test target performs a Python compile check inside the application
image. It uses the same image, storage mount, env mount, GPU runtime, IPC, and
host networking assumptions as the app container.
