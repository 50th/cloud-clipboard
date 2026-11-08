# 方案 B：本地构建镜像 → 传输 → 部署

> **状态：已实施并验证（2026-11-08）。**
> 线上容器已切换为 `cloud-clipboard-api:1.0.0` / `cloud-clipboard-web:1.0.0`。
> Nginx 配置、证书、迁移文件仍随源码包同步；服务器构建保留为回退路径。

**最后更新**：2026-11-08

## 1. 网络与构建验证结果

| 检查项 | 结果 |
|--------|------|
| `nginx:alpine` | 可拉取 |
| `python:3.13-slim` | 可拉取 |
| `node:24-alpine` | 可拉取 |
| 本机 npm registry | 可用（慢，但成功） |
| 本机本地构建 `api` | 成功，镜像 **222 MB** |
| 本机本地构建 `web` | 成功，镜像 **63.2 MB** |
| 两个镜像导出后大小 | 未压缩 **280.4 MB**，gzip 后 **94.9 MB** |
| 构建耗时 | api 约 19 分钟、web 约 4 分钟（当前网络下 pip/npm 下载约 30 KB/s） |

### 构建时发现的阻塞点

Dockerfile 首行：

```
# syntax=docker/dockerfile:1
```

会让 BuildKit 去 Docker Hub 拉取 `docker/dockerfile:1` 前端镜像，而当前网络下
`auth.docker.io` 会超时，导致构建直接失败。

**验证结果**：去掉这一行后，`api` 与 `web` 均能成功构建。
本项目未使用该前端镜像的高级特性，建议直接删除这两行。

## 2. 目标改造清单

| 文件 | 改动 |
|------|------|
| `server/Dockerfile` | 删除 `# syntax=docker/dockerfile:1` |
| `web/Dockerfile` | 删除 `# syntax=docker/dockerfile:1` |
| `deploy/docker-compose.prod.yml` | `api` / `web` 增加 `image: cloud-clipboard-{api,web}:${IMAGE_TAG}`，保留 `build` |
| `deploy/.env.example` | 增加 `IMAGE_TAG=1.0.0` |
| `scripts/build_release.ps1`（新增） | 本地构建、打 tag、`docker save` 压缩成发布包 |
| `scripts/deploy_release.ps1`（新增） | 上传发布包、`docker load`、可选迁移、`up -d`、健康检查 |
| `docs/deployment.md` | 补充方案 B 的操作流程 |

可选但推荐：

- 固定基础镜像 digest，避免本地与服务器构建结果漂移：
  - `python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`
  - `node:24-alpine@sha256:a34ab6d7f6f4813f4d0c5469d74685604b962fbdbf5793a7bc7b4998ecb867c8`
  - `nginx:alpine@sha256:713fc2ebfd92e8217db451477182ee91944b123d2b1ee9fd5a8c6e91ca6c3a11`

## 3. 新流程

```
本地测试通过
  → 本地构建 api / web 镜像（固定版本 tag）
  → docker save + gzip
  → scp 到服务器
  → docker load
  → （有迁移）备份数据库 → alembic upgrade head
  → docker compose up -d
  → 健康检查与冒烟
```

### 3.1 构建（本地）

```powershell
# 先确保测试通过
cd server; $env:PYTHONUTF8='1'; .\venv\Scripts\python.exe -m pytest
.\scripts\run_web_tests.ps1 -PnpmPath "C:\Users\shouw\AppData\Roaming\npm\pnpm.cmd"

# 构建
docker build --platform linux/amd64 -t cloud-clipboard-api:1.0.0 server
docker build --platform linux/amd64 `
  --build-arg VITE_API_BASE_URL=https://43.134.121.173:8443 `
  -t cloud-clipboard-web:1.0.0 web

# 导出发布包
docker save cloud-clipboard-api:1.0.0 cloud-clipboard-web:1.0.0 `
  | gzip > release-1.0.0.tar.gz
```

### 3.2 部署（服务器）

```bash
gunzip -c /tmp/release-1.0.0.tar.gz | docker load
cd /opt/cloud-clipboard

# 有迁移时先备份
sudo docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U clipboard clipboard | gzip > backup-$(date +%F-%H%M).sql.gz

sudo docker compose -f deploy/docker-compose.prod.yml run --rm api alembic upgrade head
sudo docker compose -f deploy/docker-compose.prod.yml up -d
curl -k https://127.0.0.1:8443/health
```

> `deploy/.env` 需同步设置 `IMAGE_TAG=1.0.0`，否则 Compose 会找不到镜像。

## 4. 回滚

- 保留每次的 `release-<tag>.tar.gz`；
- 回滚时 `docker load` 旧包，把 `deploy/.env` 的 `IMAGE_TAG` 改回旧版本，再 `up -d`；
- 数据库迁移不回滚，破坏性变更前必须先备份。

## 5. 风险与注意事项

1. **本机构建速度受网络影响**：当前 pip 约 30 KB/s，api 首次构建近 20 分钟；网络改善后会明显加快。
2. **构建架构必须是 `linux/amd64`**：服务器是 x86_64；Apple Silicon 必须显式 `--platform linux/amd64`。
3. **`VITE_API_BASE_URL` 必须是生产地址**：构建期写入，写错会导致前端连到 localhost。
4. **发布包较大**：约 95 MB（gzip），scp 时间取决于本机上行带宽。
5. **Compose 的 `image:` 与 `build:` 同时存在时**：`up -d` 使用已有镜像；只有显式 `--build` 才重新构建。部署时不要误加 `--build`。
6. **源码/配置仍需同步**：Compose、Nginx 配置、证书、迁移文件仍通过 `git archive` 传输；方案 B 只改变镜像生产方式。
7. **本地必须先跑完整测试**：方案 B 把生产镜像的构建责任移到本地，测试不过就不应出包。
8. **基础镜像 digest 固定为可选项**：固定后本地必须先预拉取，网络差时更依赖预拉取。

## 6. 验收标准

1. 本地两端测试全部通过；
2. 本地镜像 tag 与 `IMAGE_TAG` 一致；
3. 服务器 `docker load` 成功，`up -d` 无报错；
4. `/health` 返回 200；
5. 注册（邀请码）、登录、保存、多标签同步正常；
6. 回滚演练：加载上一个发布包后可恢复运行。

## 7. 确认后实施顺序

1. 删除两个 Dockerfile 的 `# syntax` 行；
2. Compose 增加 `image:`，`.env.example` 增加 `IMAGE_TAG`；
3. 新增 `build_release.ps1` / `deploy_release.ps1`；
4. 更新 `docs/deployment.md`；
5. 本地构建并导出一个测试版本；
6. 在服务器执行一次完整的“加载 → 迁移 → 启动 → 验收”；
7. 验证回滚流程；
8. 提交并推送。

## 8. 实施结果（2026-11-08）

- 本地出包：`release-1.0.0.tar.gz` 97.4 MB；`api` 222 MB、`web` 63.2 MB。
- 服务器 `docker load` 成功，容器切换为：
  - `cloud-clipboard-api:1.0.0`
  - `cloud-clipboard-web:1.0.0`
- 部署脚本自动备份数据库到 `/opt/cloud-clipboard/backups/`。
- `alembic upgrade head` 通过（无新迁移）。
- 验证：内部 `/health` 200；外部 HTTPS 200；未登录 API 返回 401。
- 回滚演练：切换到旧服务器镜像 tag `0.9.0` → 健康检查通过；再切回 `1.0.0` → 健康检查通过。
- 首次部署脚本曾因 `IMAGE_TAG` 插值失败；已改为显式 `export IMAGE_TAG` +
  `sudo env IMAGE_TAG=... docker compose` 注入。

---

方案 2 已实施并完成验证。
