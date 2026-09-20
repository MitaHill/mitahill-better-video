#!/usr/bin/env bash
# 在远程运行器上执行，不在本机运行。由 deploy.sh 通过 SSH（bash -s）送过去，
# 工作目录是远程运行目录（docker-compose.yaml 所在处），环境变量 TAG 是要部署的镜像标签。
set -euo pipefail
REPO=kindmitaishere/mitahill-better-video
export TAG

# .env 不存在时 docker 会把挂载点建成目录，先保证它是文件（内容可为空）
if [ -d .env ]; then rmdir .env; fi
[ -f .env ] || touch .env

echo "-- 停止并删除容器"
docker compose down --remove-orphans

old=$(docker images -q "$REPO:$TAG")
echo "-- 拉取 $REPO:$TAG"
docker compose pull --quiet
new=$(docker images -q "$REPO:$TAG")

echo "-- 启动"
docker compose up -d --force-recreate

# 拉取成功并启动后再删旧镜像，网络失败时不会留下空窗
if [ -n "$old" ] && [ "$old" != "$new" ]; then
  docker rmi "$old" >/dev/null && echo "已删除旧镜像 $old"
fi
# 切换标签时，本项目仓库里其他标签的旧镜像也一并删除
docker images "$REPO" --format '{{.Tag}}' | { grep -vx "$TAG" || true; } | while read -r t; do
  docker rmi "$REPO:$t" >/dev/null && echo "已删除旧标签镜像 $REPO:$t"
done
if [ -n "$(docker images -q better_video:latest)" ]; then
  docker rmi better_video:latest >/dev/null && echo "已删除旧的本地构建镜像 better_video:latest"
fi

echo "-- 等待 /api/health（启动自检会跑一个小 GPU 任务，最多 120 秒）"
ok=0
for _ in $(seq 1 60); do
  if out=$(curl -fsS -m 3 localhost:8501/api/health 2>/dev/null); then
    echo "健康检查通过：$out"; ok=1; break
  fi
  sleep 2
done

echo "-- 反馈：镜像、容器、日志"
docker images "$REPO" --format '镜像 {{.Repository}}:{{.Tag}}  {{.ID}}  创建于 {{.CreatedSince}}'
docker compose ps
echo "日志中 traceback/error 行数：$(docker compose logs better_video 2>&1 | grep -ciE 'traceback|error' || true)"
docker compose logs --tail=15 better_video 2>&1
[ "$ok" = 1 ] || { echo "健康检查超时" >&2; exit 1; }
