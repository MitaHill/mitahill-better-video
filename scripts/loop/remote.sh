#!/usr/bin/env bash
# 远程连接：读取 remote_key.json，封装 SSH 调用。由 dev-loop.sh 引入。

json_field() {
  python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print("" if v is None else v)' \
    "$KEY_JSON" "$1"
}

load_remote() {
  [ -f "$KEY_JSON" ] || die "缺少 $KEY_JSON，请参考同目录的 remote_key.example.json 创建"
  # 凭据文件必须被忽略，否则拒绝继续，避免被 git add / commit 带走
  git check-ignore -q "$KEY_JSON" || die "remote_key.json 没有被 .gitignore 忽略，拒绝继续"
  chmod 600 "$KEY_JSON"

  local host user
  host=$(json_field host); user=$(json_field user)
  [ -n "$host" ] && [ -n "$user" ] || die "remote_key.json 需要填写 host 和 user"
  REMOTE_HOST="$user@$host"
  SSH_PORT=$(json_field port); SSH_PORT="${SSH_PORT:-22}"
  SSH_KEY=$(json_field key_file); SSH_KEY="${SSH_KEY/#\~/$HOME}"
  SSH_PASSWORD=$(json_field password)
  REMOTE_DIR=$(json_field remote_dir); REMOTE_DIR="${REMOTE_DIR:-/root/mitahill-better-video}"
}

# 所有连接共用一个 ControlMaster，只认证一次
remote() {
  local opts=(-p "$SSH_PORT" -o ControlMaster=auto -o "ControlPath=$HOME/.ssh/cm-%C"
              -o ControlPersist=1h -o ConnectTimeout=10)
  if [ -n "$SSH_KEY" ]; then
    ssh "${opts[@]}" -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes "$REMOTE_HOST" "$@"
  elif [ -n "$SSH_PASSWORD" ]; then
    # 密码通过 SSH_ASKPASS 提供，不出现在命令行参数里
    local askpass; askpass=$(mktemp)
    printf '#!/bin/sh\nprintf "%%s\\n" "$REMOTE_PASSWORD"\n' > "$askpass"; chmod 700 "$askpass"
    local rc=0
    REMOTE_PASSWORD="$SSH_PASSWORD" SSH_ASKPASS="$askpass" SSH_ASKPASS_REQUIRE=force DISPLAY=none \
      ssh "${opts[@]}" -o PubkeyAuthentication=no "$REMOTE_HOST" "$@" || rc=$?
    rm -f "$askpass"
    return "$rc"
  else
    ssh "${opts[@]}" -o BatchMode=yes "$REMOTE_HOST" "$@"
  fi
}

check_remote() {
  remote true 2>/dev/null \
    || die "无法连接 $REMOTE_HOST:$SSH_PORT。请检查 remote_key.json 中的 key_file / password，
或先在终端建立一条免密连接：ssh -o ControlMaster=yes -o ControlPath=~/.ssh/cm-%C -o ControlPersist=1h -fN $REMOTE_HOST"
}
