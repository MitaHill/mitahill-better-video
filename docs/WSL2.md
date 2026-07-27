# WSL2 部署提示

WSL2 下运行本项目时，先确认 Windows 已安装 NVIDIA 驱动，WSL 内可以执行：

```bash
nvidia-smi
```

再确认 Docker 可以调用 GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

仓库根目录提供快速部署脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/MitaHill/mitahill-better-video/main/scripts/quick-start.sh | bash
```

`quick-start` 会检测环境并拉取项目，随后运行 `quick-deploy`。脚本检测到 WSL2 后，会自动附加 `scripts/quick-deploy-src/docker-compose.wsl2.yaml`，用于挂载 WSL2 NVIDIA 动态库。
如果 Docker 或 NVIDIA Container Toolkit 缺失，可以使用：

```bash
curl -fsSL https://raw.githubusercontent.com/MitaHill/mitahill-better-video/main/scripts/quick-start.sh | bash -s -- --install-deps
```

## 常见问题

### unknown or invalid runtime name: nvidia

安装 NVIDIA Container Toolkit，配置 Docker runtime：

```bash
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo service docker restart
```

### failed to discover GPU vendor from CDI

生成 CDI 配置：

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
sudo service docker restart
```

### root 找不到 nvidia-smi

WSL2 的 `nvidia-smi` 通常在 `/usr/lib/wsl/lib/`：

```bash
sudo ln -sf /usr/lib/wsl/lib/nvidia-smi /usr/bin/nvidia-smi
```

### 容器缺少 NVIDIA 动态库

如果日志出现 `libcuda.so`、`libnvidia-encode.so.1` 相关错误，快速部署脚本会通过 WSL2 覆盖文件加入：

```yaml
environment:
  - LD_LIBRARY_PATH=/usr/lib/wsl/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
volumes:
  - /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro
```

修改后重建容器：

```bash
docker compose down
docker compose up -d --force-recreate
```
