# 生产部署方案

> **状态：部署文件已创建，尚未在服务器验证。**
> 已落地：两个 Dockerfile、生产 Compose、Nginx 配置与变量模板（见第 3 节）。
> 本机因 Docker Hub 不可达，镜像构建与 `nginx -t` 均未实测；
> 进度与验收记录仍以 [`roadmap.md`](roadmap.md) 为准。

**最后更新**：2026-11-06
**目标版本**：v1.0.0（仅文字剪贴板）

## 1. 已确认的前提

| 项 | 决策 |
|----|------|
| 部署形态 | **单台云服务器 + Docker Compose** |
| 域名 | **暂无域名**，先用服务器 IP 访问 |
| 反向代理 | **Nginx 托管静态资源 + 反代 API / WebSocket** |
| 数据库 | PostgreSQL 16 容器，与本地版本一致 |
| 后端 | FastAPI + uvicorn，**强制单 worker** |

选择依据：仓库现有 `infra/docker-compose.yml` 已用容器跑 PostgreSQL，生产沿用容器化可以保持一致；
WebSocket 广播是进程内实现，单机单容器即可满足，无需 Redis。

## 2. 目标架构

```
浏览器 ──HTTPS / WSS──> Nginx (宿主 8443 → 容器 443)
                          ├─ /            → dist 静态文件（SPA fallback）
                          └─ /api/**      → api 容器 :8000（FastAPI，单 worker）
                                               └─> db 容器 :5432（PostgreSQL 16）
```

- `db` 与 `api` **不向宿主机发布端口**，只在 Compose 内部网络互通。
- 宿主端口通过 `WEB_HTTP_PORT` / `WEB_HTTPS_PORT` 配置，默认 `8080` / `8443`；
  80 / 443 被其他业务占用时无需改动容器内监听端口。
- HTTP 只做 301 跳转到 HTTPS。

## 3. 已创建的部署文件

| 文件 | 作用 |
|------|------|
| `server/Dockerfile` | `python:3.13-slim` 基础镜像，安装 `requirements.txt`，非 root 运行，`uvicorn --host 0.0.0.0 --port 8000`（**不传 `--workers`**） |
| `web/Dockerfile` | 多阶段构建：`node:24-alpine` 执行 `pnpm build` → `nginx:alpine` 托管 `dist` |
| `deploy/docker-compose.prod.yml` | 编排 `db` / `api` / `web` 三个服务，配置健康检查、重启策略、日志轮转 |
| `deploy/nginx/nginx.conf` | 主配置：HTTP→HTTPS 跳转、TLS、日志格式（不含 query string）、登录限流 |
| `deploy/nginx/locations.conf` | 站点路由：SPA fallback、静态缓存、API / WS 反代、dev 路由拦截（HTTP/HTTPS 共用） |
| `deploy/.env.example` | Compose 变量模板（`POSTGRES_*`、端口、`VITE_API_BASE_URL`、证书说明） |
| `server/.dockerignore`、`web/.dockerignore` | 排除 `venv`、`node_modules`、`.env`、`logs`、`dist` |

> 生产 Compose 与开发用的 `infra/docker-compose.yml` **保持独立**，不要复用同一份文件。

### 3.1 前端地址在构建期固定

`VITE_API_BASE_URL` 会被 Vite 编译进 bundle，运行时无法改：

- 无域名阶段：`VITE_API_BASE_URL=https://<服务器IP>:8443`（自签证书）
- 正式域名后：`VITE_API_BASE_URL=https://<域名>`，WS 地址自动推导为 `wss://`
- **不能留空**：源码中空值会回退到 `http://127.0.0.1:8000`（见 `web/src/api/client.ts`）
- 不同主机部署才需要单独配 `VITE_WS_URL`；同源反代无需配置

因此：**服务器 IP / 域名 / 协议变更都需要重新构建 web 镜像**。

## 4. 服务器准备

| 项 | 建议 |
|----|------|
| 配置 | 2 vCPU / 2 GB 内存 / 40 GB 磁盘起步 |
| 系统 | Ubuntu 22.04 或 24.04，时区 `Asia/Shanghai` |
| 账号 | 创建非 root 运维用户，启用 2 GB swap |
| 防火墙 | 云安全组 + UFW 仅放行 22 与站点端口（默认 8080 / 8443） |
| Docker | Docker Engine + Compose 插件（不要用 Docker Desktop） |
| 镜像源 | 国内服务器拉取 `postgres:16`、`python:3.13-slim`、`node:24-alpine`、`nginx:alpine` 可能失败，需配置国内 registry 镜像，或 `docker save` / `docker load` 离线导入 |
| npm 源 | web 镜像构建走 `web/.npmrc` 的 `registry.npmjs.org`；国内构建慢或失败时可临时改用镜像源 |
| SSH | 禁用密码登录，只允许密钥；改完先用新会话验证可登录再断开旧连接 |

## 5. 生产环境变量

生产变量写在服务器上的 `server/.env`（`chmod 600`，已被 `.gitignore` 忽略）。

| 变量 | 生产值 | 说明 |
|------|--------|------|
| `APP_ENV` | `production` | 否则弱密钥启动拦截不生效（`server/app/core/config.py`） |
| `JWT_SECRET` | `openssl rand -base64 48` 生成 | ≥32 字节；禁止沿用开发默认值 |
| `DATABASE_URL` | `postgresql+asyncpg://clipboard:<强密码>@db:5432/clipboard` | **主机名是 Compose 服务名 `db`**，不是 `127.0.0.1` |
| `DEBUG` | `false` | 不向响应暴露错误详情 |
| `ENABLE_DEV_ROUTES` | `false` | 关闭 `/api/v1/dev/*`（含删数据的 reset） |
| `LOG_FILE` | 空 | 容器内输出到 stdout，由 Docker 采集 |
| `LOG_CONSOLE` | `false` | 与上一项配合即可 |
| `CORS_ORIGINS` | 站点自身 origin | 同源反代下可保持最小列表 |
| `DEMO_PASSWORD` | 不播种 | 生产**不执行**带种子数据的初始化 |

`deploy/.env` 额外变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_HTTP_PORT` | `8080` | 宿主机 HTTP 端口，仅做 HTTPS 跳转 |
| `WEB_HTTPS_PORT` | `8443` | 宿主机 HTTPS 端口 |
| `VITE_API_BASE_URL` | 必填 | 构建期写入前端 bundle |

## 6. 首次部署步骤

在服务器上按顺序执行（仓库根目录为 `/opt/cloud-clipboard`）：

1. **初始化服务器**：Docker Engine、镜像源；按需调整云安全组。
2. **获取代码**：`git clone` 后切到目标 tag / 分支，或用 `git archive` 传输。
3. **写生产变量**：复制 `deploy/.env.example` 为 `deploy/.env`（Compose 变量插值），
   复制 `server/.env.example` 为 `server/.env` 并按第 5 节填写，确认权限 600。
4. **生成自签证书**（无域名阶段）：
   ```bash
   mkdir -p deploy/certs
   openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
     -keyout deploy/certs/privkey.pem \
     -out deploy/certs/fullchain.pem \
     -subj "/CN=<服务器IP>" \
     -addext "subjectAltName=IP:<服务器IP>"
   chmod 600 deploy/certs/privkey.pem
   ```
5. **构建镜像**（`VITE_API_BASE_URL` 已在 `deploy/.env` 中）：
   ```bash
   docker compose -f deploy/docker-compose.prod.yml build
   ```
6. **启动数据库并等待健康**：
   ```bash
   docker compose -f deploy/docker-compose.prod.yml up -d db
   ```
7. **执行迁移**：
   ```bash
   docker compose -f deploy/docker-compose.prod.yml run --rm api alembic upgrade head
   ```
   > 生产**不要执行** `scripts.init_db` 的播种流程，避免出现 `demo / demo1234` 演示账号。
8. **启动全部服务**：
   ```bash
   docker compose -f deploy/docker-compose.prod.yml up -d
   ```
9. **验证**：`curl -k https://<服务器IP>:8443/health` 应返回 `{"status":"ok"}`。
10. **创建首个账号**：通过页面注册并登录。
11. **按第 9 节清单验收**。

## 7. HTTPS 方案（暂无域名）

浏览器剪贴板写入 API 只在**安全上下文**下可用。三种选择：

| 方案 | 做法 | 代价 |
|------|------|------|
| A. HTTP + IP（临时） | 前端构建用 `http://<IP>` | 明文传输令牌与剪贴板内容，**不推荐** |
| B. 自签证书 + IP SAN（当前采用） | `openssl req -x509 ... -addext "subjectAltName=IP:<IP>"`，Nginx 在 8443 提供 HTTPS | 浏览器证书警告；需手动信任证书后 `navigator.clipboard` 才可用，否则走 `execCommand` 降级 |
| C. 域名 + ICP 备案 + Let's Encrypt | 正规生产路径 | 备案周期以实际为准 |

当前部署采用 **B**：宿主 `8080` 做 301 跳转到 `8443`，证书放在 `deploy/certs/`。
域名与备案就绪后切到 **C**：把 `WEB_HTTPS_PORT` 改回 `443`、替换证书、更新
`VITE_API_BASE_URL` 与 `CORS_ORIGINS`，并重新构建 web 镜像。

## 8. Nginx 反代要点

1. **SPA fallback**：`try_files $uri $uri/ /index.html`。
2. **API 反代**：`location /api/ { proxy_pass http://api:8000; }`，保留原始路径。
3. **WebSocket**：必须带升级头：
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection $connection_upgrade;
   proxy_read_timeout 3600s;
   ```
4. **Token 日志脱敏**：WS 的令牌在 query string（`?token=<JWT>`）。访问日志用 `$uri` 而不是 `$request_uri`，
   或对该 location 关闭 `access_log`；**不得让明文 token 落盘**。
5. **拦截内部入口**：`/docs`、`/redoc`、`/openapi.json`、`/api/v1/dev/*` 返回 404。
6. **登录限流**：对 `/api/v1/auth/login` 配置 `limit_req`，防口令爆破。
7. **请求体上限**：按文字剪贴板需求设置 `client_max_body_size`（如 1 MB）。

## 9. 验收清单

1. `GET https://<IP>:8443/health` 返回 200（自签证书需加 `-k`）。
2. 注册 / 登录成功；错误口令返回 401。
3. 保存、列表、搜索、排序、分页、编辑、删除、清空全部正常。
4. 两个浏览器标签页之间实时同步（WS 经 Nginx 反代正常）。
5. 手机浏览器访问，移动端「历史记录 / 剪贴板输入」页签布局正常。
6. 「复制」按钮可用（HTTPS 或 `execCommand` 降级路径）。
7. 后端日志中 WS 令牌显示为 `token=***`；Nginx 访问日志无明文 token。
8. 重启服务器后容器自动拉起，数据仍在。

## 10. 运维

### 备份

- 宿主机 cron 每天执行 `pg_dump`，压缩后保留 7 天。
- 至少一份备份复制到对象存储或另一台机器。
- 定期做恢复演练，确认备份可用。

### 日志

- 容器日志走 Docker `json-file` 驱动，配置 `max-size: 10m`、`max-file: 5`。
- 应用日志由 `LOG_FILE=` 输出到 stdout，不再写容器内文件。

### 发布

1. `git pull` 并切到新 tag。
2. 重建镜像（打版本 tag，保留上一版）。
3. `alembic upgrade head`。
4. `up -d`。

### 回滚

- 切回上一版镜像 tag 后重启。
- 数据库迁移**不做自动回滚**；涉及破坏性变更前必须先备份。

### 监控

- 至少监控 `/health`、磁盘、内存。
- 排障以日志中的 `request_id` 为对齐线索。

## 11. 安全加固

- 安全组 / UFW 只放行 22 与站点端口（默认 8080 / 8443）；`5432` 与 `8000` 绝不发布到宿主。
- 容器以非 root 运行，`restart: unless-stopped`。
- 确认 `server/.env` 与 `deploy/.env` 权限 600 且未被提交到仓库。
- 生产关闭 `DEBUG` 与 `ENABLE_DEV_ROUTES`，Nginx 再兜底拦截 dev 路由与文档入口。
- **本次实际部署按用户要求暂未修改系统安全配置**（SSH 密码登录与 UFW 保持现状），
  上线后建议尽快补做：禁用 SSH 密码登录、启用 UFW、安装 fail2ban。

## 12. 已知限制与待决策

### 已知限制

1. **后端只能单 worker**：WebSocket 广播是进程内实现，多 worker 会「数据一致但推送丢事件」。
   要横向扩容必须先引入 Redis Pub/Sub。
2. **无域名阶段使用自签证书**，浏览器会警告，且未信任时剪贴板写入 API 不可用
   （「复制」会走 `execCommand` 降级）。
3. **前端后端地址是构建期常量**，IP / 域名 / 协议变更必须重新构建镜像。
4. **PostgreSQL 固定 16**：与本地一致，避免跨大版本 `pg_dump/pg_restore` 不兼容。

### 待决策

- 域名购买与 ICP 备案的启动时间（决定何时能从方案 A 切到 C）。
- **注册接口当前对所有人开放**：生产前需决定是否加邀请码 / 白名单 / 关闭注册。
- 是否长期拦截 `/docs` 等文档入口（当前应用本身始终注册这些路由）。
- 服务器镜像源方案：配置 registry 镜像，还是离线导入本地已有的 `postgres:16`。
