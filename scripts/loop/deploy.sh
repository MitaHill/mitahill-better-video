#!/usr/bin/env bash
# 远程部署（本机侧）。由 dev-loop.sh 引入。

deploy() {
  local tag="${DEPLOY_TAG:-dev}"
  load_remote
  check_remote
  log "远程停止旧容器、拉取 :$tag 镜像并重建"
  # 远程只保存 docker-compose.yaml、.env 和 storage/，重部署逻辑由本机通过 SSH 送过去执行
  remote "cd $REMOTE_DIR && TAG=$tag bash -s" < "$LOOP_DIR/remote-run.sh"

  printf '\n页面：http://%s:8501\n' "${REMOTE_HOST#*@}"
  echo "行为改动请在页面提交一个小任务，确认完成并能在管理页删除。"
  echo "满意：到此结束。不满意：修改代码后再执行 scripts/loop/dev-loop.sh ship \"提交信息\"。"
}
