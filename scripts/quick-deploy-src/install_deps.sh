#!/usr/bin/env bash

install_docker() {
  if have docker && docker compose version >/dev/null 2>&1; then
    return 0
  fi

  info "$(msg installing_docker)"
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  curl -fsSL https://get.docker.com | sh
}

install_nvidia_toolkit() {
  have nvidia-ctk && return 0

  info "$(msg installing_toolkit)"
  apt-get update
  apt-get install -y ca-certificates curl gnupg

  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt-get update
  apt-get install -y nvidia-container-toolkit
}

configure_nvidia_runtime() {
  have nvidia-ctk || return 0

  nvidia-ctk runtime configure --runtime=docker

  if [ "$IS_WSL" -eq 1 ]; then
    mkdir -p /etc/cdi
    nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml >/dev/null 2>&1 || true
  fi

  restart_docker
}

fix_wsl_nvidia_smi() {
  if [ "$IS_WSL" -ne 1 ]; then
    return 0
  fi

  if have nvidia-smi || [ ! -x /usr/lib/wsl/lib/nvidia-smi ]; then
    return 0
  fi

  info "$(msg wsl_nvidia_link)"
  ln -sf /usr/lib/wsl/lib/nvidia-smi /usr/bin/nvidia-smi
}

install_missing_deps() {
  need_root
  info "$(msg installing_deps)"
  install_docker
  install_nvidia_toolkit
  configure_nvidia_runtime
  fix_wsl_nvidia_smi
  info "$(msg install_finished)"
}

missing_deps() {
  local missing=0

  have docker || missing=1
  docker compose version >/dev/null 2>&1 || missing=1
  have nvidia-ctk || missing=1

  return "$missing"
}

maybe_offer_install() {
  if missing_deps; then
    return 0
  fi

  check_gpu
  check_network
  warn "$(msg deps_missing)"

  if confirm "$(msg install_prompt)"; then
    INSTALL_DEPS=1
    install_missing_deps
    return 0
  fi

  fail "$(msg install_declined)"
}
