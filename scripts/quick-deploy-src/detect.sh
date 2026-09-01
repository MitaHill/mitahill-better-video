#!/usr/bin/env bash

check_root() {
  if [ "$(id -u)" -ne 0 ]; then
    warn "$(msg root_warn)"
  else
    info "$(msg running_root)"
  fi
}

check_debian() {
  [ -r /etc/os-release ] || fail "$(msg unsupported_os)"

  # shellcheck disable=SC1091
  . /etc/os-release

  case "${ID:-} ${ID_LIKE:-}" in
    *debian*|*ubuntu*)
      info "$(msg debian_ok): ${PRETTY_NAME:-unknown}"
      ;;
    *)
      fail "$(msg unsupported_os): ${PRETTY_NAME:-unknown}"
      ;;
  esac
}

detect_wsl() {
  IS_WSL=0

  if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=1
  fi

  if grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; then
    IS_WSL=1
  fi

  if [ "$IS_WSL" -eq 1 ]; then
    info "$(msg wsl_detected)"
  else
    info "$(msg linux_detected)"
  fi
}

check_gpu() {
  local nvidia_smi="nvidia-smi"

  if ! have nvidia-smi && [ "$IS_WSL" -eq 1 ] && [ -x /usr/lib/wsl/lib/nvidia-smi ]; then
    nvidia_smi="/usr/lib/wsl/lib/nvidia-smi"
    if [ "$(id -u)" -eq 0 ]; then
      fix_wsl_nvidia_smi
      nvidia_smi="nvidia-smi"
    fi
  fi

  command -v "$nvidia_smi" >/dev/null 2>&1 || fail "$(msg nvidia_missing)"
  "$nvidia_smi" >/tmp/mitahill-better-video-nvidia-smi.log 2>&1 || {
    cat /tmp/mitahill-better-video-nvidia-smi.log >&2
    fail "$(msg nvidia_failed)"
  }
  info "$(msg nvidia_ok)"
}

check_docker() {
  have docker || fail "$(msg docker_missing)"
  docker info >/dev/null 2>&1 || fail "$(msg docker_daemon_failed)"
  docker compose version >/dev/null 2>&1 || fail "$(msg compose_missing)"
  have nvidia-ctk || fail "$(msg toolkit_missing)"
  info "$(msg docker_ok)"
}

check_network() {
  have curl || have wget || fail "$(msg network_tool_missing)"
  check_http "internet" "https://www.cloudflare.com/cdn-cgi/trace"
  check_http "dockerhub" "https://registry-1.docker.io/v2/"
  check_http "github" "https://github.com/"
}

check_docker_gpu() {
  local image="${GPU_TEST_IMAGE:-nvidia/cuda:12.1.1-base-ubuntu22.04}"

  info "$(msg docker_gpu_check): $image"
  docker run --rm --gpus all "$image" nvidia-smi >/tmp/mitahill-better-video-docker-gpu.log 2>&1 || {
    cat /tmp/mitahill-better-video-docker-gpu.log >&2
    fail "$(msg docker_gpu_failed)"
  }
  info "$(msg docker_gpu_ok)"
}

check_disk() {
  local available_gb

  available_gb="$(df -BG "$ROOT_DIR" | awk 'NR == 2 {gsub(/G/, "", $4); print $4}')"
  if [ "${available_gb:-0}" -lt 32 ]; then
    warn "$(msg disk_low): ${available_gb:-unknown}GB"
  else
    info "$(msg disk_ok): ${available_gb}GB"
  fi
}

check_port() {
  local found=0

  if have ss; then
    local details

    details="$(ss -ltnp 2>/dev/null | awk '$4 ~ /(^|:)8501$/ {print}')"
    if [ -n "$details" ]; then
      warn "$(msg port_busy)"
      printf '%s\n' "$details" >&2
      found=1
    else
      info "$(msg port_free)"
    fi
    return
  fi

  if have lsof; then
    if lsof -nP -iTCP:8501 -sTCP:LISTEN 2>/dev/null; then
      warn "$(msg port_busy)"
      found=1
    else
      info "$(msg port_free)"
    fi
    return
  fi

  if have netstat; then
    local netstat_details

    netstat_details="$(netstat -ltnp 2>/dev/null | awk '$4 ~ /(^|:)8501$/ {print}')"
    if [ -n "$netstat_details" ]; then
      warn "$(msg port_busy)"
      printf '%s\n' "$netstat_details" >&2
      found=1
    else
      info "$(msg port_free)"
    fi
    return
  fi

  [ "$found" -eq 0 ] && warn "$(msg port_unknown)"
}

check_compose_files() {
  docker compose -f "$ROOT_DIR/deploy/compose/docker-compose.build.yml" config >/dev/null
  (cd "$ROOT_DIR/pre-run" && docker compose config >/dev/null)

  if [ "$IS_WSL" -eq 1 ]; then
    docker compose \
      -f "$ROOT_DIR/pre-run/docker-compose.yaml" \
      -f "$ROOT_DIR/scripts/quick-deploy-src/docker-compose.wsl2.yaml" \
      config >/dev/null
  fi

  info "$(msg compose_ok)"
}

run_checks() {
  check_gpu
  check_docker
  check_network
  check_docker_gpu
  check_disk
  check_port
  check_compose_files
}
