#!/usr/bin/env bash

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
    return
  fi

  if [ -e /etc/localtime ]; then
    readlink /etc/localtime 2>/dev/null | sed 's#.*zoneinfo/##'
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
      deploy_usage) echo "用法: bash scripts/quick-deploy.sh [--check-only] [--skip-build] [--install-deps]" ;;
      usage_check_only) echo "只检查宿主机环境" ;;
      usage_skip_build) echo "跳过镜像构建，只重建运行容器" ;;
      usage_install_deps) echo "尝试安装缺失的 Docker 与 NVIDIA Container Toolkit" ;;
      usage_help) echo "显示帮助" ;;
      unknown_option) echo "未知参数" ;;
      deploy_needs_repo) echo "quick-deploy 必须在项目仓库内运行，请先运行 quick-start 拉取项目" ;;
      root_warn) echo "本项目最好通过root用户运行，以普通用户运行可能会出现未知错误" ;;
      running_root) echo "当前使用 root 用户运行" ;;
      install_needs_root) echo "--install-deps 需要 root 用户" ;;
      debian_ok) echo "已检测到 Debian/Ubuntu 系统" ;;
      unsupported_os) echo "当前系统不受支持，需要 Debian 或 Ubuntu" ;;
      wsl_detected) echo "已检测到 WSL2 环境" ;;
      linux_detected) echo "已检测到标准 Linux 环境" ;;
      nvidia_missing) echo "未找到 nvidia-smi" ;;
      nvidia_failed) echo "nvidia-smi 执行失败" ;;
      nvidia_ok) echo "NVIDIA GPU 可用" ;;
      docker_missing) echo "未找到 Docker，若需要自动安装请追加 --install-deps" ;;
      docker_daemon_failed) echo "Docker daemon 不可用，若需要自动安装请追加 --install-deps" ;;
      compose_missing) echo "Docker Compose 插件不可用，若需要自动安装请追加 --install-deps" ;;
      toolkit_missing) echo "NVIDIA Container Toolkit 不可用，若需要自动安装请追加 --install-deps" ;;
      docker_ok) echo "Docker 与 Docker Compose 可用" ;;
      deps_missing) echo "已确认 NVIDIA GPU 和互联网可用，但 Docker 或 NVIDIA Container Toolkit 缺失" ;;
      install_prompt) echo "是否允许脚本安装 Docker 与 NVIDIA Container Toolkit？" ;;
      install_declined) echo "依赖缺失，已取消自动安装" ;;
      network_tool_missing) echo "需要 curl 或 wget 执行网络检查" ;;
      reachable) echo "可连接" ;;
      unreachable) echo "不可连接" ;;
      docker_gpu_check) echo "正在检查 Docker GPU 调用能力" ;;
      docker_gpu_failed) echo "Docker 容器无法调用 NVIDIA GPU" ;;
      docker_gpu_ok) echo "Docker GPU 调用正常" ;;
      disk_low) echo "可用磁盘空间偏低，推荐 32GB 以上" ;;
      disk_ok) echo "可用磁盘空间" ;;
      port_busy) echo "8501 端口已被占用，可能已有 better_video 容器在运行" ;;
      port_free) echo "8501 端口未被监听" ;;
      port_unknown) echo "未找到 ss/lsof/netstat，无法确认 8501 端口是否被占用" ;;
      compose_ok) echo "Compose 配置合法" ;;
      check_only_finished) echo "环境检查完成" ;;
      docker_restart_manual) echo "无法自动重启 Docker，请手动重启 Docker 后重试" ;;
      installing_deps) echo "开始安装缺失依赖" ;;
      installing_docker) echo "正在安装 Docker" ;;
      installing_toolkit) echo "正在安装 NVIDIA Container Toolkit" ;;
      install_finished) echo "依赖安装完成" ;;
      wsl_nvidia_link) echo "正在创建 WSL2 nvidia-smi 软链接" ;;
      skip_build) echo "跳过镜像构建" ;;
      build_base) echo "开始构建基础镜像" ;;
      build_app) echo "开始构建应用镜像" ;;
      start_standard) echo "按标准 Linux 方式启动容器" ;;
      start_wsl) echo "按 WSL2 方式启动容器" ;;
      web_url) echo "访问地址" ;;
      *) echo "$key" ;;
    esac
    return
  fi

  case "$key" in
    usage) echo "Usage: bash scripts/quick-start.sh [quick-deploy options]" ;;
    deploy_usage) echo "Usage: bash scripts/quick-deploy.sh [--check-only] [--skip-build] [--install-deps]" ;;
    usage_check_only) echo "only check the host environment" ;;
    usage_skip_build) echo "skip image build and recreate the runtime container" ;;
    usage_install_deps) echo "try to install missing Docker and NVIDIA Container Toolkit" ;;
    usage_help) echo "show help" ;;
    unknown_option) echo "unknown option" ;;
    deploy_needs_repo) echo "quick-deploy must run inside the project repo. Run quick-start first" ;;
    root_warn) echo "Running as root is recommended for this project. Running as a normal user may cause unknown errors" ;;
    running_root) echo "running as root" ;;
    install_needs_root) echo "--install-deps requires root" ;;
    debian_ok) echo "Debian/Ubuntu family detected" ;;
    unsupported_os) echo "unsupported system. Debian or Ubuntu is required" ;;
    wsl_detected) echo "WSL2 detected" ;;
    linux_detected) echo "standard Linux detected" ;;
    nvidia_missing) echo "nvidia-smi not found" ;;
    nvidia_failed) echo "nvidia-smi failed" ;;
    nvidia_ok) echo "NVIDIA GPU available" ;;
    docker_missing) echo "Docker not found. Add --install-deps if you want the script to install it" ;;
    docker_daemon_failed) echo "Docker daemon is not available. Add --install-deps if you want the script to install dependencies" ;;
    compose_missing) echo "Docker Compose plugin is not available. Add --install-deps if you want the script to install it" ;;
    toolkit_missing) echo "NVIDIA Container Toolkit is not available. Add --install-deps if you want the script to install it" ;;
    docker_ok) echo "Docker and Docker Compose available" ;;
    deps_missing) echo "NVIDIA GPU and internet are available, but Docker or NVIDIA Container Toolkit is missing" ;;
    install_prompt) echo "Allow this script to install Docker and NVIDIA Container Toolkit?" ;;
    install_declined) echo "required dependencies are missing and automatic installation was declined" ;;
    network_tool_missing) echo "curl or wget is required for network checks" ;;
    reachable) echo "reachable" ;;
    unreachable) echo "unreachable" ;;
    docker_gpu_check) echo "checking Docker GPU runtime" ;;
    docker_gpu_failed) echo "Docker cannot use NVIDIA GPU" ;;
    docker_gpu_ok) echo "Docker GPU runtime available" ;;
    disk_low) echo "available disk is low. 32GB+ is recommended" ;;
    disk_ok) echo "available disk" ;;
    port_busy) echo "port 8501 is already listening. Existing better_video container may be running" ;;
    port_free) echo "port 8501 is not listening" ;;
    port_unknown) echo "ss/lsof/netstat not found. Port 8501 cannot be confirmed" ;;
    compose_ok) echo "Compose files are valid" ;;
    check_only_finished) echo "check only finished" ;;
    docker_restart_manual) echo "Docker could not be restarted automatically. Restart Docker manually and retry" ;;
    installing_deps) echo "installing missing dependencies" ;;
    installing_docker) echo "installing Docker" ;;
    installing_toolkit) echo "installing NVIDIA Container Toolkit" ;;
    install_finished) echo "dependency installation finished" ;;
    wsl_nvidia_link) echo "creating WSL2 nvidia-smi symlink" ;;
    skip_build) echo "skip image build" ;;
    build_base) echo "building base image" ;;
    build_app) echo "building app image" ;;
    start_standard) echo "starting container for standard Linux" ;;
    start_wsl) echo "starting container for WSL2" ;;
    web_url) echo "web ui" ;;
    *) echo "$key" ;;
  esac
}
