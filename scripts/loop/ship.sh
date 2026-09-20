#!/usr/bin/env bash
# 前置检查、同步、提交推送并等待构建。由 dev-loop.sh 引入。

check() {
  prog_next
  need_dev
  gh auth status >/dev/null 2>&1 || die "gh 未登录，请先 gh auth login"
  load_remote
  check_remote
  prog_end done "分支 ${BRANCH}，gh 已登录，${REMOTE_HOST} 可连接"
}

sync() {
  prog_next
  need_dev
  git diff --quiet && git diff --cached --quiet || die "有未提交的改动，请先提交或暂存"
  prog_dirty
  git pull --ff-only origin "$BRANCH"
  prog_end done
}

ship() {
  local msg="${1:-}"
  check

  prog_next
  if ! git diff --quiet || ! git diff --cached --quiet; then
    [ -n "$msg" ] || die "有未提交的改动，请给出提交信息：scripts/loop/dev-loop.sh ship \"fix: ...\""
    prog_dirty
    git add -u
    git commit -m "$msg"
    prog_end done
  else
    prog_end skip "工作区干净，直接推送已有提交"
  fi

  prog_next
  git fetch origin "$BRANCH"
  git merge-base --is-ancestor "origin/$BRANCH" HEAD \
    || die "远程 $BRANCH 有本机没有的提交，请先执行 scripts/loop/dev-loop.sh sync"

  local sha
  sha=$(git rev-parse HEAD)
  if git log -1 --format=%B | grep -qF '[skip ci]'; then
    die "最新提交含 [skip ci]，不会触发构建，无镜像可部署"
  fi

  prog_dirty
  git push origin "$BRANCH"
  prog_end done "${sha:0:7}"

  prog_next
  local run_id=""
  for _ in $(seq 1 30); do
    run_id=$(gh run list --workflow "$WORKFLOW" --branch "$BRANCH" --commit "$sha" \
      --limit 1 --json databaseId --jq '.[0].databaseId // empty')
    [ -n "$run_id" ] && break
    sleep 4
  done
  [ -n "$run_id" ] || die "2 分钟内没有找到该提交触发的构建，请到 Actions 页面查看"

  prog_dirty
  if ! gh run watch "$run_id" --interval 15 --exit-status; then
    log "构建或测试失败，失败步骤日志（末尾 80 行）"
    gh run view "$run_id" --log-failed | tail -80
    die "构建失败，未部署。修改代码后重新执行 scripts/loop/dev-loop.sh ship \"提交信息\""
  fi
  prog_end done "构建与镜像内单测通过"

  deploy
}
