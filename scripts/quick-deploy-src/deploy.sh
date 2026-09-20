#!/usr/bin/env bash

build_images() {
  if [ "$SKIP_BUILD" -eq 1 ]; then
    info "$(msg skip_build)"
    return
  fi

  cd "$ROOT_DIR"
  info "$(msg build_base)"
  docker compose -f deploy/compose/docker-compose.build.yml build base_image
  info "$(msg build_app)"
  docker compose -f deploy/compose/docker-compose.build.yml build app_image
}

start_container() {
  cd "$ROOT_DIR/pre-run"

  # .env 被 git 忽略，缺失时 compose 会把挂载源建成目录
  [ -d .env ] && rmdir .env
  [ -e .env ] || touch .env

  if [ "$IS_WSL" -eq 1 ]; then
    info "$(msg start_wsl)"
    docker compose \
      -f docker-compose.yaml \
      -f ../scripts/quick-deploy-src/docker-compose.wsl2.yaml \
      up -d --force-recreate
    docker compose \
      -f docker-compose.yaml \
      -f ../scripts/quick-deploy-src/docker-compose.wsl2.yaml \
      ps
  else
    info "$(msg start_standard)"
    docker compose up -d --force-recreate
    docker compose ps
  fi

  info "$(msg web_url): http://127.0.0.1:8501"
}

deploy() {
  build_images
  start_container
}
