# pre-run 运行约定

此目录是默认运行入口。

- 所有启动、重启、联调操作均在 `pre-run/` 下执行。
- 持久化数据固定写入 `pre-run/storage/`：
  - 上传文件
  - 输出文件
  - 数据库
  - 日志
  - 转录模型缓存
- `pre-run/.env` 会挂载到容器 `/workspace/config/.env`。

示例：

```bash
cd pre-run
docker compose up -d
docker compose ps
docker compose logs --tail=200 better_video
```
