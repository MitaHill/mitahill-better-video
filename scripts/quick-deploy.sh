#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$SCRIPT_DIR/quick-deploy-src"

CHECK_ONLY=0
SKIP_BUILD=0
INSTALL_DEPS=0
IS_WSL=0

# shellcheck source=scripts/quick-deploy-src/lang.sh
. "$SRC_DIR/lang.sh"
# shellcheck source=scripts/quick-deploy-src/common.sh
. "$SRC_DIR/common.sh"
# shellcheck source=scripts/quick-deploy-src/detect.sh
. "$SRC_DIR/detect.sh"
# shellcheck source=scripts/quick-deploy-src/install_deps.sh
. "$SRC_DIR/install_deps.sh"
# shellcheck source=scripts/quick-deploy-src/deploy.sh
. "$SRC_DIR/deploy.sh"

usage() {
  cat <<EOF
$(msg deploy_usage)

  --check-only    $(msg usage_check_only)
  --skip-build    $(msg usage_skip_build)
  --install-deps  $(msg usage_install_deps)
  -h, --help      $(msg usage_help)
EOF
}

if [ ! -f "$ROOT_DIR/deploy/compose/docker-compose.build.yml" ] || [ ! -f "$ROOT_DIR/pre-run/docker-compose.yaml" ]; then
  fail "$(msg deploy_needs_repo)"
fi

for arg in "$@"; do
  case "$arg" in
    --check-only)
      CHECK_ONLY=1
      ;;
    --skip-build)
      SKIP_BUILD=1
      ;;
    --install-deps)
      INSTALL_DEPS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "$(msg unknown_option): $arg"
      ;;
  esac
done

check_root
check_debian
detect_wsl

if [ "$INSTALL_DEPS" -eq 0 ]; then
  maybe_offer_install
else
  install_missing_deps
fi

run_checks

if [ "$CHECK_ONLY" -eq 1 ]; then
  info "$(msg check_only_finished)"
  exit 0
fi

deploy
