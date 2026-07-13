# 项目文档

这里放运行、开发和排障需要长期保留的文档。README 只写快速入口，具体规则以本目录文档为准。

## 文档索引

- [运行 SOP](SOP.md)：日常开发、构建、验证、Git 和版本规则。
- [架构说明](ARCHITECTURE.md)：进程模型、模块边界、存储路径和关键约束。
- [API 说明](API.md)：任务、管理、转录、下载等接口。
- [WSL2 部署提示](WSL2.md)：WSL2 下 NVIDIA / Docker 常见问题。
- [真实 IP 部署](DEPLOY_REAL_IP.md)：Nginx、FRP、Proxy Protocol 配置。
- [第三方代码与模型](THIRD_PARTY.md)：外部代码、模型来源和许可证。
- [Compose 工作流](../deploy/compose/README.md)：构建、开发、测试 Compose 文件。

## 标准运行入口

```bash
cd pre-run
docker compose up -d
docker compose ps
docker compose logs --tail=200 better_video
```

持久化数据在 `pre-run/storage/`：

- `upload/`：上传源文件
- `output/`：输出结果和任务临时目录
- `data/tasks.db`：SQLite 数据库
- `logs/`：运行日志
- `models/`：运行期模型缓存

## 开发基线

- 新功能、修复和文档改动从 `dev` 开始。
- `main` 只放已验证、可发布的稳定版本。
- 每个 `dev` 提交都要先完成必要验证。
- 版本号带 `alpha` 或 `beta` 后缀时，GitHub Release 必须标记为预览版。
- 版本号没有后缀时，GitHub Release 才标记为正式发行版。

## 项目原则

代码和文档都遵循同一条原则：

> 易实现、稳健、最小改动、简单。

不要为假想需求增加复杂抽象。前端只暴露真实生效的配置项。后端失败要清晰报错，不做静默降级。
