#!/usr/bin/env bash

set -Eeuo pipefail

REPO_URL="${BETTER_VIDEO_REPO:-https://github.com/MitaHill/mitahill-better-video.git}"
TARGET_DIR="${BETTER_VIDEO_DIR:-${HOME:-/root}/dev/mitahill-better-video}"
INSTALL_DEPS=0

detect_timezone() {
  if [ -n "${TZ:-}" ]; then
    printf '%s' "$TZ"
    return
  fi

  if command -v timedatectl >/dev/null 2>&1; then
    timedatectl show -p Timezone --value 2>/dev/null && return
  fi

  if [ -r /etc/timezone ]; then
    sed -n '1p' /etc/timezone
  fi
}

TEXT_LANG="en"
case "$(detect_timezone)" in
  Asia/Shanghai|Asia/Taipei|Asia/Hong_Kong|Asia/Macau)
    TEXT_LANG="zh"
    ;;
esac

msg() {
  local key="$1"

  if [ "$TEXT_LANG" = "zh" ]; then
    case "$key" in
      usage) echo "用法: bash scripts/quick-start.sh [quick-deploy 参数]" ;;
      root_warn) echo "本项目最好通过root用户运行，以普通用户运行可能会出现未知错误" ;;
      unsupported_os) echo "当前系统不受支持，需要 Debian 或 Ubuntu" ;;
      nvidia_missing) echo "未找到 nvidia-smi" ;;
      nvidia_failed) echo "nvidia-smi 执行失败" ;;
      network_missing) echo "无法连接互联网或 GitHub" ;;
      git_missing) echo "未找到 git，若需要自动安装请在 quick-deploy 阶段允许安装依赖" ;;
      git_install_prompt) echo "未找到 git，是否允许脚本安装 git？" ;;
      git_install_declined) echo "缺少 git，无法拉取项目" ;;
      installing_git) echo "正在安装 git" ;;
      clone_repo) echo "正在拉取项目" ;;
      update_repo) echo "项目目录已存在，正在同步代码" ;;
      run_deploy) echo "开始运行部署脚本" ;;
      *) echo "$key" ;;
    esac
    return
  fi

  case "$key" in
    usage) echo "Usage: bash scripts/quick-start.sh [quick-deploy options]" ;;
    root_warn) echo "Running as root is recommended for this project. Running as a normal user may cause unknown errors" ;;
    unsupported_os) echo "unsupported system. Debian or Ubuntu is required" ;;
    nvidia_missing) echo "nvidia-smi not found" ;;
    nvidia_failed) echo "nvidia-smi failed" ;;
    network_missing) echo "internet or GitHub is unreachable" ;;
    git_missing) echo "git not found. Allow dependency installation in quick-deploy if needed" ;;
    git_install_prompt) echo "git not found. Allow this script to install git?" ;;
    git_install_declined) echo "git is missing. The project cannot be cloned" ;;
    installing_git) echo "installing git" ;;
    clone_repo) echo "cloning project" ;;
    update_repo) echo "project directory exists, updating code" ;;
    run_deploy) echo "running deploy script" ;;
    *) echo "$key" ;;
  esac
}

info() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

confirm() {
  local prompt="$1"
  local answer

  if [ ! -t 0 ]; then
    return 1
  fi

  printf '%s [y/N] ' "$prompt"
  read -r answer

  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

check_root() {
  if [ "$(id -u)" -ne 0 ]; then
    warn "$(msg root_warn)"
  fi
}

check_debian() {
  [ -r /etc/os-release ] || fail "$(msg unsupported_os)"

  # shellcheck disable=SC1091
  . /etc/os-release

  case "${ID:-} ${ID_LIKE:-}" in
    *debian*|*ubuntu*) ;;
    *) fail "$(msg unsupported_os): ${PRETTY_NAME:-unknown}" ;;
  esac
}

check_gpu() {
  have nvidia-smi || fail "$(msg nvidia_missing)"
  nvidia-smi >/tmp/mitahill-better-video-start-nvidia-smi.log 2>&1 || {
    cat /tmp/mitahill-better-video-start-nvidia-smi.log >&2
    fail "$(msg nvidia_failed)"
  }
}

check_network() {
  if have curl; then
    curl -L --connect-timeout 10 --max-time 20 -o /dev/null -sS https://github.com/ || fail "$(msg network_missing)"
    return
  fi

  if have wget; then
    wget --spider --timeout=20 https://github.com/ >/dev/null 2>&1 || fail "$(msg network_missing)"
    return
  fi

  fail "$(msg network_missing)"
}

fetch_repo() {
  if ! have git; then
    if [ "$(id -u)" -eq 0 ] && { [ "$INSTALL_DEPS" -eq 1 ] || confirm "$(msg git_install_prompt)"; }; then
      info "$(msg installing_git)"
      apt-get update
      apt-get install -y git ca-certificates curl
    else
      fail "$(msg git_install_declined)"
    fi
  fi

  if [ -d "$TARGET_DIR/.git" ]; then
    info "$(msg update_repo): $TARGET_DIR"
    git -C "$TARGET_DIR" pull --ff-only
    return
  fi

  info "$(msg clone_repo): $TARGET_DIR"
  mkdir -p "$(dirname "$TARGET_DIR")"
  git clone "$REPO_URL" "$TARGET_DIR"
}

usage() {
  msg usage
}

for arg in "$@"; do
  case "$arg" in
    --install-deps)
      INSTALL_DEPS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
done

check_root
check_debian
check_gpu
check_network
fetch_repo

info "$(msg run_deploy)"
exec bash "$TARGET_DIR/scripts/quick-deploy.sh" "$@"
