#!/usr/bin/env bash

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

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    fail "$(msg install_needs_root)"
  fi
}

restart_docker() {
  if have systemctl; then
    systemctl restart docker >/dev/null 2>&1 && return 0
  fi

  if have service; then
    service docker restart >/dev/null 2>&1 && return 0
  fi

  warn "$(msg docker_restart_manual)"
}

http_code() {
  local url="$1"

  if have curl; then
    curl -L --connect-timeout 10 --max-time 20 -o /dev/null -sS -w '%{http_code}' "$url" || true
    return
  fi

  if have wget; then
    wget --spider --timeout=20 "$url" >/dev/null 2>&1 && printf '200' || true
    return
  fi

  printf '000'
}

check_http() {
  local name="$1"
  local url="$2"
  local code

  code="$(http_code "$url")"
  case "$code" in
    200|204|301|302|307|308|401|403)
      info "$name $(msg reachable) ($code)"
      ;;
    *)
      fail "$name $(msg unreachable): $url (http $code)"
      ;;
  esac
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
