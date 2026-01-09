# 未来功能规划：VoiceFixer 音频增强

**状态**: 规划中 / 草案
**目标约束**: < 4GB 显存 (生产环境安全水位: 3.5GB)
**选定模型**: VoiceFixer (修复 + 超分辨率)

## 1. 背景与动机
当前应用程序仅复制原始音轨 (`-c:a copy`) 而不做增强。用户期望音频质量能升级以匹配放大后的视频画质。
**关键约束**: 生产环境有 4GB 显存的硬性限制。如果同时运行 Real-ESRGAN（消耗约 3.5GB）和音频模型，将导致 OOM（显存溢出）崩溃。

## 2. 技术选型

### 为什么选择 VoiceFixer?
- **能力**: 与简单的降噪器 (DeepFilterNet) 不同，VoiceFixer 提供 **修复** (修复削波/退化) 和 **频带扩展** (音频超分辨率)，使其成为 Real-ESRGAN 的完美音频搭档。
- **资源适配**: 
  - 推理显存: ~2.0 - 2.8 GB (如果串行运行，完全在 3.5GB 安全限制内)。
  - 存储: < 300 MB 权重文件。
- **许可证**: MIT (开源)。

### 舍弃的备选方案
- **DeepFilterNet**: 显存极低 (<1GB)，但仅能降噪，缺乏用户期望的“高保真”修复能力。
- **Demucs**: 主要用于源分离。若不进行激进的分段设置，显存占用可能过高。

## 3. 架构设计：串行处理

为了严格遵守 4GB 限制，我们 **不能** 并行运行视频和音频增强。必须采用 **加载-运行-卸载** 策略。

### 处理流程
1.  **阶段 1: 视频放大**
    - 加载 `Real-ESRGAN` (显存: ~3.5GB)
    - 处理视频帧
    - **卸载 `Real-ESRGAN`** -> `gc.collect()` -> `torch.cuda.empty_cache()` (显存: ~0.1GB)
2.  **阶段 2: 音频增强**
    - 提取音频 (`ffmpeg`)
    - 加载 `VoiceFixer` (显存: ~2.5GB)
    - 处理音频 (分块处理)
    - **卸载 `VoiceFixer`** -> `gc.collect()` -> `torch.cuda.empty_cache()` (显存: ~0.1GB)
3.  **阶段 3: 封装合成**
    - 合并放大后的视频 + 增强后的音频 (`ffmpeg`)

## 4. 实施计划

### A. 基础镜像 (Dockerfile.base)
我们必须将依赖和权重“固化”在基础镜像中，以避免运行时下载（网络限制策略）。

**修改 `deploy/docker/Dockerfile.base`**:
1.  **安装库**: `pip install voicefixer`
2.  **预下载权重**:
    - 创建目录: `/workspace/weights/voicefixer`
    - 下载 `analysis_module.ckpt` (Zenodo/HF)
    - 下载 `model.ckpt-1490000_trimed.pt` (Zenodo/HF)

### B. 应用镜像 (Dockerfile.app)
**修改 `deploy/docker/Dockerfile.app`**:
- 在构建时创建软链接，以便 VoiceFixer 自动找到模型：
  `mkdir -p /root/.cache/voicefixer/analysis_module/checkpoints`
  `ln -s /workspace/weights/voicefixer/analysis_module.ckpt ...`

### C. 核心逻辑 (`app/src_worker/audio_enhancer.py`)
创建一个包装类 `AudioEnhancer`:
- **init**: 轻量级，不加载模型。
- **process(input_path, output_path)**:
  - `load_model()`: 实例化 VoiceFixer (移至 GPU)。
  - `voicefixer.restore(...)`: 运行处理。
  - `unload_model()`: 删除实例，调用 `torch.cuda.empty_cache()`。

### D. Worker 集成 (`app/worker.py`)
修改主任务循环以插入阶段 2。
- 添加配置检查: `if config.ENABLE_AUDIO_ENHANCEMENT:`
- 确保异常处理: 如果音频失败，回退到原始音频 (故障安全)。

## 5. 模型权重下载地址
- **分析模块**: `https://huggingface.co/Diogodiogod/voicefixer-models/resolve/main/vf.ckpt` (重命名为 `analysis_module.ckpt`)
- **合成模块**: `https://huggingface.co/Diogodiogod/voicefixer-models/resolve/main/model.ckpt-1490000_trimed.pt`

## 6. 风险与缓解
- **风险**: 阶段 1 结束后显存碎片化导致无法完全释放。
  - *缓解*: 如果 `empty_cache()` 不够，运行一个“哑”小张量分配/释放循环，或者为音频 Worker 使用子进程（但这会增加复杂性）。
- **风险**: 长音频文件导致 OOM。
  - *缓解*: VoiceFixer 处理分块，但我们必须验证默认的分块大小是保守的。
