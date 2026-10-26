#!/usr/bin/env bash
# 远程部署（本机侧）。由 dev-loop.sh 引入。

deploy() {
  local tag="${DEPLOY_TAG:-dev}"
  local image="${DEPLOY_IMAGE:-kindmitaishere/mitahill-better-video:$tag}"
  [[ "$image" =~ ^kindmitaishere/mitahill-better-video:([a-zA-Z0-9_.-]+)$ ]] \
    || die "无效的部署镜像引用"
  prog_next
  load_remote
  check_remote
  # 远程只保存 docker-compose.yaml、.env 和 storage/，重部署逻辑由本机通过 SSH 送过去执行
  prog_dirty
  local quoted_dir
  printf -v quoted_dir '%q' "$REMOTE_DIR"
  remote "cd $quoted_dir && IMAGE_REF=$image bash -s" < "$LOOP_DIR/remote-run.sh"
  prog_end done "已部署 ${image}（上一镜像已保留）"

  printf '\n页面：http://%s:8501\n' "${REMOTE_HOST#*@}"
  echo "行为改动请在页面提交一个小任务，确认完成并能在管理页删除。"
  echo "满意：到此结束。不满意：修改代码后再执行 scripts/loop/dev-loop.sh ship \"提交信息\"。"
}
