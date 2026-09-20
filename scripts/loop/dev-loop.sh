#!/usr/bin/env bash
# 本机开发循环：提交 -> 推送触发构建 -> 等待 CI -> 远程拉取镜像并重建 -> 反馈
# 用法：scripts/loop/dev-loop.sh [ship ["提交信息"]|sync|deploy|check]
#   ship    有改动时先提交（需要提交信息），推送 dev，等 GitHub Actions 构建并测试通过，
#           再部署到远程并检查（默认）。只暂存已跟踪文件的改动，新文件请先 git add
#   sync    从远程仓库拉取 dev 的最新状态到本机
#   deploy  跳过提交和构建，只让远程重新拉取镜像并运行。默认 :dev 标签，
#           部署稳定版用 DEPLOY_TAG=latest scripts/loop/dev-loop.sh deploy
#   check   只检查前置条件（分支、gh 登录、remote_key.json、远程 SSH 连接）
#
# 模块：
#   remote.sh      读取 remote_key.json、封装 SSH 调用
#   ship.sh        check / sync / ship
#   deploy.sh      deploy（本机侧）
#   remote-run.sh  通过 SSH 送到远程执行的重部署脚本，不在本机运行
# 远程连接信息见 remote_key.example.json，实际使用的 remote_key.json 已被 .gitignore 忽略。
set -Eeuo pipefail

LOOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$LOOP_DIR/../.." && pwd)"
BRANCH=dev
WORKFLOW=build-images.yml
KEY_JSON="$LOOP_DIR/remote_key.json"

cd "$ROOT_DIR"

log() { printf '\n==> %s\n' "$*"; }
die() { printf '错误：%s\n' "$*" >&2; exit 1; }

need_dev() {
  [ "$(git branch --show-current)" = "$BRANCH" ] \
    || die "当前不在 $BRANCH 分支。main 的推送会清空 Docker Hub 仓库，请先 git switch $BRANCH"
}

# shellcheck source=scripts/loop/remote.sh
. "$LOOP_DIR/remote.sh"
# shellcheck source=scripts/loop/deploy.sh
. "$LOOP_DIR/deploy.sh"
# shellcheck source=scripts/loop/ship.sh
. "$LOOP_DIR/ship.sh"

case "${1:-ship}" in
  ship) ship "${2:-}" ;;
  sync) sync ;;
  deploy) deploy ;;
  check) check ;;
  *) die "未知参数：$1（可用：ship sync deploy check）" ;;
esac
