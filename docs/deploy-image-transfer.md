# 方案 B：本地出包与制品部署

> **状态：已实施并验证（2026-11-08）。**
> 本文只记录方案决策与验证结果；日常操作见
> [`deployment.md`](deployment.md) 的「6.1 方案 B」与「10. 运维」。

## 为什么切换

服务器构建会占用生产 CPU / 内存，并要求服务器能访问 Docker Hub。
改为**本地构建镜像 → 传输制品 → 服务器加载**：

- 构建资源转移到开发机；
- 镜像按版本 tag 固化，回滚更快；
- 服务器只负责 `docker load` 与启动。

## 验证结果

| 项 | 结果 |
|----|------|
| `nginx:alpine` / `python:3.13-slim` / `node:24-alpine` | 本机可拉取 |
| `cloud-clipboard-api` / `web` | 222 MB / 63.2 MB |
| 发布包 `release-1.0.0.tar.gz` | 97.4 MB（gzip） |
| 首次构建耗时 | api 约 19 分钟、web 约 4 分钟（当时 pip/npm 约 30 KB/s） |

## 关键改动

- 两个 Dockerfile 删除 `# syntax=docker/dockerfile:1`
  （否则 BuildKit 需从 `auth.docker.io` 拉取构建前端，网络不稳时直接失败）。
- Compose 增加固定镜像名，保留 `build` 作为回退：
  `cloud-clipboard-api:${IMAGE_TAG}`、`cloud-clipboard-web:${IMAGE_TAG}`。
- `deploy/.env` 增加 `IMAGE_TAG`。
- 新增 [`build_release.ps1`](../scripts/build_release.ps1) 与
  [`deploy_release.ps1`](../scripts/deploy_release.ps1)。

## 使用

```powershell
# 出包（要求工作区干净）
.\scripts\build_release.ps1 -ApiBaseUrl "https://43.134.121.173:8443" -Tag "1.0.0"

# 上传、加载、备份、迁移、切换、健康检查
.\scripts\deploy_release.ps1 -Tag "1.0.0"
```

产物在 `dist/`（已被 git 忽略）：

- `release-<tag>.tar.gz`：api + web 镜像
- `source-<tag>.tar.gz`：已提交源码（Compose / Nginx / 迁移）

## 注意事项

1. **架构必须是 `linux/amd64`**：服务器为 x86_64；Apple Silicon 需显式
   `--platform linux/amd64`。
2. **`VITE_API_BASE_URL` 是构建期常量**：必须是生产地址，写错会导致前端连到 localhost。
3. **`up -d` 不要加 `--build`**：否则会在服务器重新构建。
4. **源码 / 配置仍需同步**：部署脚本会自动上传并解压源码包。
5. **发布包约 97 MB**：传输时间取决于本机上行带宽。

## 实施结果

- 容器已切换为 `cloud-clipboard-api:1.0.0` / `cloud-clipboard-web:1.0.0`。
- 部署前自动备份数据库；`alembic upgrade head` 通过。
- 内部 `/health` 200；外部 HTTPS 200；未登录 API 401。
- 回滚演练：切到旧服务器镜像 tag `0.9.0` → 健康；再切回 `1.0.0` → 健康。
- 首次部署曾因 `IMAGE_TAG` 插值失败，已改为 `export IMAGE_TAG` +
  `sudo env IMAGE_TAG=... docker compose` 注入。
