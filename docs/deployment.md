# 生产部署方案

> **状态：已部署到 43.134.121.173（HTTPS 8443，自签证书）。**
> 容器全部健康，API 冒烟测试通过（注册 / 创建 / 列表 / 删除），`/health` 正常。
> 已启用数据库邀请码（有效期 / 使用次数 / 撤销，见第 10 节）与注册/登录限流。
> 云安全组已放行 TCP 8443，公网 HTTPS 与邀请码注册已验证通过。
> 当前镜像改为**本地构建 + 制品传输**（方案 B），见 [`deploy-image-transfer.md`](deploy-image-transfer.md)；
> 服务器构建保留为回退路径。
> 进度与验收记录仍以 [`roadmap.md`](roadmap.md) 为准。

**最后更新**：2026-11-10
**当前线上版本**：v1.0.0（文字剪贴板）
**待发布**：后台管理 `/admin`（迁移 `0003` + `0004`，需 `scripts.set_admin` 指定管理员）

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
| `deploy/.env.example` | Compose 变量模板（`POSTGRES_*`、端口、`IMAGE_TAG`、`VITE_API_BASE_URL`、证书说明） |
| `scripts/build_release.ps1` | 本地构建镜像、打 tag、导出 `release-<tag>.tar.gz` 与源码包 |
| `scripts/deploy_release.ps1` | 上传发布包、`docker load`、备份、迁移、切换并做健康检查 |
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
| 镜像源 | 可直连 Docker Hub 时无需配置；拉取失败时再用镜像源或离线导入 |
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
| `REGISTRATION_REQUIRE_INVITE` | `true` | 开启后注册必须使用 `invite_codes` 表中的有效邀请码 |
| `ADMIN_JWT_EXPIRE_MINUTES` | `720` | 管理员令牌有效期（默认 12 小时），比普通用户更短 |

`deploy/.env` 额外变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_HTTP_PORT` | `8080` | 宿主机 HTTP 端口，仅做 HTTPS 跳转 |
| `WEB_HTTPS_PORT` | `8443` | 宿主机 HTTPS 端口 |
| `IMAGE_TAG` | `1.0.0` | 本地构建的镜像版本 tag；回滚时改回旧版本 |
| `VITE_API_BASE_URL` | 必填 | 构建期写入前端 bundle |

## 6. 首次部署步骤

当前生产使用**方案 B（本地出包 + 制品传输）**。服务器构建保留为回退方案。

### 6.1 方案 B（当前）

1. **初始化服务器**：Docker Engine、镜像源；云安全组放行站点端口。
2. **部署源码与配置**：
   - 把已提交源码解压到 `/opt/cloud-clipboard`（`git archive` 或 `scp`）；
   - 按第 5 节创建 `server/.env`；如需后台管理，设置 `ADMIN_JWT_EXPIRE_MINUTES`；
   - 复制 `deploy/.env.example` 为 `deploy/.env`，填写 `POSTGRES_*`、`IMAGE_TAG`、
     `VITE_API_BASE_URL`；
   - 生成自签证书（见本节末尾）。
3. **启动数据库**：
   ```bash
   sudo docker compose -f deploy/docker-compose.prod.yml up -d db
   ```
4. **本地出包**：
   ```powershell
   .\scripts\build_release.ps1 -ApiBaseUrl "https://<服务器IP>:8443" -Tag "<new-tag>"
   ```
5. **上传并部署**：
   ```powershell
   .\scripts\deploy_release.ps1 -Tag "<new-tag>"
   ```
   脚本会依次：解压源码 → 更新 `IMAGE_TAG` → `docker load` → 备份数据库 →
   `alembic upgrade head` → `up -d` → 健康检查。
6. **创建首个账号**，并按第 9 节验收。
7. **（后台管理）初始化管理员**：一条命令完成建号 + 授权
   ```bash
   cd /opt/cloud-clipboard
   sudo docker compose -f deploy/docker-compose.prod.yml run --rm -it api \
     python -m scripts.set_admin --username admin --email admin@example.com --create
   ```
   已有账号时去掉 `--create` 只做授权；非交互场景追加 `--password-stdin` 并从 stdin 传密码。
   然后按 [`admin.md`](admin.md) 的 §8.3 配置管理端网络边界。

> 首次部署时数据库为空，脚本里的 `pg_dump` 只是空库备份，属正常。

**自签证书（无域名阶段）：**

```bash
mkdir -p deploy/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout deploy/certs/privkey.pem \
  -out deploy/certs/fullchain.pem \
  -subj "/CN=<服务器IP>" \
  -addext "subjectAltName=IP:<服务器IP>"
chmod 600 deploy/certs/privkey.pem
```

### 6.2 回退：服务器构建

不依赖本地 Docker 的回退路径：

1. 初始化服务器、获取代码、写 `deploy/.env`（含 `IMAGE_TAG`）与 `server/.env`。
2. 生成自签证书（同上）。
3. 构建并启动：
   ```bash
   sudo docker compose -f deploy/docker-compose.prod.yml build
   sudo docker compose -f deploy/docker-compose.prod.yml up -d db
   sudo docker compose -f deploy/docker-compose.prod.yml run --rm api alembic upgrade head
   sudo docker compose -f deploy/docker-compose.prod.yml up -d
   ```
4. 验证 `curl -k https://<服务器IP>:8443/health`。
5. 生产**不要执行** `scripts.init_db` 的播种流程，避免出现 `demo / demo1234`。

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
2. **API 反代**：`location /api/ { proxy_pass http://api_backend; }`，保留原始路径。
3. **WebSocket**：必须带升级头：
   ```nginx
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection $connection_upgrade;
   proxy_read_timeout 3600s;
   ```
4. **Token 日志脱敏**：WS 的令牌在 query string（`?token=<JWT>`）。访问日志用 `$uri` 而不是 `$request_uri`，
   或对该 location 关闭 `access_log`；**不得让明文 token 落盘**。
5. **内部入口**：`/docs`、`/redoc`、`/openapi.json` 不在 `/api/` 反代范围内，
   公网不会暴露后端文档；`/api/v1/dev/*` 明确返回 404。
6. **登录与注册限流**：登录 `/api/v1/auth/login` 每 IP 10 次/分钟，注册
   `/api/v1/auth/register` 每 IP 5 次/分钟，防口令爆破与批量注册。
7. **请求体上限**：按文字剪贴板需求设置 `client_max_body_size`（当前 2 MB）。

## 9. 验收清单

1. `GET https://<IP>:8443/health` 返回 200（自签证书需加 `-k`）。
2. 注册 / 登录成功；错误口令返回 401。
3. 保存、列表、搜索、排序、分页、编辑、删除、清空全部正常。
4. 两个浏览器标签页之间实时同步（WS 经 Nginx 反代正常）。
5. 手机浏览器访问，移动端「历史记录 / 剪贴板输入」页签布局正常。
6. 「复制」按钮可用（HTTPS 或 `execCommand` 降级路径）。
7. 后端日志中 WS 令牌显示为 `token=***`；Nginx 访问日志无明文 token。
8. 重启服务器后容器自动拉起，数据仍在。
9. （后台管理）`scripts.set_admin` 后 `/admin` 可登录；普通用户访问返回 403；
   非白名单网络无法访问管理端与 `/api/v1/admin/`。

## 10. 运维

### 邀请码管理

邀请码存放在 `invite_codes` 表，明文只在生成时输出一次（库里只存哈希）。
推荐用后台 `/admin` 的「邀请码」页：可设置**最大使用次数**、有效期、查看使用详情与撤销。
CLI 作为兜底（生产容器内执行）：

```bash
# 生成（--label 备注邀请对象；--max-uses 0 表示不限次数）
sudo docker compose -f deploy/docker-compose.prod.yml run --rm api \
  python -m scripts.invite_code create --days 7 --max-uses 1 --label "alice"

# 查看使用情况（active / expired / revoked / exhausted）
sudo docker compose -f deploy/docker-compose.prod.yml run --rm api \
  python -m scripts.invite_code list

# 撤销（按明文前 8 位或记录 id）
sudo docker compose -f deploy/docker-compose.prod.yml run --rm api \
  python -m scripts.invite_code revoke --hint ABCD1234
```

### 备份

- 宿主机 cron 每天执行 `pg_dump`，压缩后保留 7 天。
- 至少一份备份复制到对象存储或另一台机器。
- 定期做恢复演练，确认备份可用。

### 日志

- 容器日志走 Docker `json-file` 驱动，配置 `max-size: 10m`、`max-file: 5`。
- 应用日志由 `LOG_FILE=` 输出到 stdout，不再写容器内文件。

### 发布

1. 本地跑完后端 + Web 测试。
2. 出包：
   ```powershell
   .\scripts\build_release.ps1 -ApiBaseUrl "https://<服务器IP>:8443" -Tag "<new-tag>"
   ```
3. 部署：
   ```powershell
   .\scripts\deploy_release.ps1 -Tag "<new-tag>"
   ```
4. 脚本自动完成备份、迁移、切换与健康检查。

### 回滚

- 保留 `dist/release-<tag>.tar.gz` 与服务器上的镜像 tag。
- 回滚：`sudo docker load` 旧发布包 → 把 `deploy/.env` 的 `IMAGE_TAG` 改回旧版本 →
  `sudo docker compose up -d`。
- 数据库迁移**不做自动回滚**；涉及破坏性变更前必须先备份。

### 监控

- 至少监控 `/health`、磁盘、内存。
- 排障以日志中的 `request_id` 为对齐线索。

## 11. 安全加固

- 安全组 / UFW 只放行 22 与站点端口（默认 8080 / 8443）；`5432` 与 `8000` 绝不发布到宿主。
- 容器以非 root 运行，`restart: unless-stopped`。
- 确认 `server/.env` 与 `deploy/.env` 权限 600 且未被提交到仓库。
- 生产关闭 `DEBUG` 与 `ENABLE_DEV_ROUTES`，Nginx 再兜底拦截 dev 路由与文档入口。
- **后台管理端仅允许内网 / VPN / IP 白名单访问**（`/admin` 与 `/api/v1/admin/` 同时限制），
  具体配置见 [`admin.md`](admin.md) 的 §8.3；管理端令牌默认 12 小时。
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

- 域名购买与 ICP 备案的启动时间（决定何时从自签证书切到正式域名证书）。
- 生产已启用数据库邀请码；本地默认开放注册（`REGISTRATION_REQUIRE_INVITE=false`）。
- 是否长期拦截 `/docs` 等文档入口（当前应用本身始终注册这些路由）。
- 网络再次不稳定时的镜像获取策略：镜像源或离线导入。
