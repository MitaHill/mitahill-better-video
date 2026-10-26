#!/usr/bin/env bash
# 由 deploy.sh 通过 SSH 送到远程运行目录执行。
set -euo pipefail
REPO=kindmitaishere/mitahill-better-video
IMAGE_REF="${IMAGE_REF:-$REPO:${TAG:-dev}}"
OVERRIDE=.deploy-image.yml

# 防止两个部署同时覆盖回滚记录或切换服务。
exec 9>.deploy.lock
flock -n 9 || { echo "已有部署正在进行" >&2; exit 1; }

compose() {
  if [ -f "$OVERRIDE" ]; then
    docker compose -f docker-compose.yaml -f "$OVERRIDE" "$@"
  else
    docker compose -f docker-compose.yaml "$@"
  fi
}

write_image() {
  printf 'services:\n  better_video:\n    image: %s\n' "$1" > "$OVERRIDE.tmp"
  mv "$OVERRIDE.tmp" "$OVERRIDE"
}

wait_healthy() {
  # 每次请求至多 3 秒，整个等待窗口至多约 120 秒。
  local deadline=$((SECONDS + ${HEALTH_TIMEOUT_SECONDS:-120})) out
  while [ "$SECONDS" -lt "$deadline" ]; do
    if out=$(curl -fsS -m 3 localhost:8501/api/health 2>/dev/null) &&
       printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("status")=="ok" and d.get("db")=="ok" and d.get("worker")=="running" else 1)'; then
      echo "健康检查通过：$out"
      return 0
    fi
    sleep 2
  done
  return 1
}

check_idle() {
  if [ -n "$old" ]; then
    docker exec better_video python3 -c 'import os,sqlite3,sys; p=os.getenv("DB_PATH", "/workspace/storage/data/tasks.db"); c=sqlite3.connect("file:"+p+"?mode=ro", uri=True); n=c.execute("SELECT COUNT(*) FROM task_queue WHERE status IN (\"PENDING\", \"PROCESSING\")").fetchone()[0]; print("活动任务:", n); sys.exit(1 if n else 0)' \
      || { echo "服务仍有活动任务或无法确认任务状态，暂缓部署" >&2; exit 1; }
  fi
}

old=$(docker inspect better_video --format '{{.Image}}' 2>/dev/null || true)
check_idle
echo "-- 先拉取 ${IMAGE_REF}，失败时当前服务继续运行"
docker pull "$IMAGE_REF"
new=$(docker image inspect "$IMAGE_REF" --format '{{.Id}}')
digest=$(docker image inspect "$IMAGE_REF" --format '{{range .RepoDigests}}{{println .}}{{end}}' | awk -v repo="$REPO@" 'index($0, repo)==1 {print; exit}')
[ -n "$digest" ] || { echo "无法取得候选镜像 digest" >&2; exit 1; }
[ "$(docker image inspect "$digest" --format '{{.Id}}')" = "$new" ] \
  || { echo "候选镜像 digest 不匹配" >&2; exit 1; }
compose config --quiet
check_idle

if [ -n "$old" ]; then
  rollback_tag="$REPO:rollback-$(date +%Y%m%d-%H%M%S)"
  docker tag "$old" "$rollback_tag"
  printf '%s\n' "$rollback_tag" > .deploy-rollback-image
  echo "回滚镜像已保留：$rollback_tag ($old)"
fi

# .env 缺失时拒绝启动，避免 Docker 将挂载点创建为目录。
[ -f .env ] || { echo ".env 必须是文件" >&2; exit 1; }
write_image "$digest"
echo "-- 切换到 $digest"
if compose up -d --force-recreate better_video && wait_healthy; then
  echo "部署成功：$IMAGE_REF -> $digest"
  compose ps
  exit 0
fi

echo "新版本启动或健康检查失败" >&2
compose logs --tail=50 better_video >&2 || true
if [ -n "$old" ]; then
  write_image "$rollback_tag"
  if compose up -d --force-recreate better_video && wait_healthy; then
    echo "已恢复上一版本：$rollback_tag" >&2
  else
    echo "回滚失败，需要人工处理；上一镜像保留为 $rollback_tag" >&2
  fi
fi
exit 1
