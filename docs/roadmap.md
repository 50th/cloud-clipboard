# 项目路线图与进度

> **本文件只记录动态进度与踩坑。** AGENTS.md 只保存稳定约定（技术栈、契约、规范、开发顺序）。
> 踩坑记录只留**会导致错误发生的机制**；实现细节看代码，过程看 git log。

**最后更新**：2026-11-10
**当前进度**：v1.0.0 已部署生产（方案 B）；后台管理已完成开发与本地验证，**待部署**；
剩余 Web 人工验收、域名与备案 → 见文末「下一步行动」

---

## 阶段划分

| 阶段 | 内容 | 版本 | 状态 |
|------|------|------|------|
| 阶段一 | 文字：保存 / 查询 / 删除 + 实时同步 + 登录 + 去重 | **v1.0.0** | ✅ 已完成，已部署生产 |
| 后台管理 | `/admin`：用户 / 剪贴板 / 邀请码 / 审计 | 随下一版本 | ✅ 已完成开发，待部署 |
| 阶段二 | 图片剪贴板 + 对象存储 | **v1.1（下一版本）** | 📋 计划中 |
| 阶段三 | 文件剪贴板 + 体验优化 | **v1.1（下一版本）** | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产加固 | 后续 | 📋 计划中 |

## 开发步骤进度

| 步骤 | 状态 | 说明 |
|------|------|------|
| 1 FastAPI 骨架 + 数据契约 | ✅ | git log `89a03e9` |
| 2 Web 端骨架 + 单端闭环 | ✅ | git log `2aa5e49` |
| 3 接入数据库 | ✅ | git log `7f055ed`、`b5cc62d`；踩坑见下 |
| 4 JWT 认证 | ✅ | 踩坑见下 |
| 5 WebSocket 实时同步 | ✅ | 踩坑见下；**强制单 worker**（P3 已决策） |
| 6 内容去重 | ✅ | 代码在第 3／5 步已落地，本步骤补齐验收覆盖 |
| 7 鸿蒙 App | ⏸️ 暂停 | 移动端交付改走 Web；代码完成、**编译通过**，暂不签名上机（踩坑见下） |
| 8 联调与测试 | 🚧 | 后端 257 项 + Web 62 项已就位；**Web 桌面/移动人工验收**待做，鸿蒙联调暂缓 |
| 9 后台管理页 | ✅ | `/admin` 用户/剪贴板/邀请码管理 + 审计；见 [`admin.md`](admin.md) |

---

## 测试现状

| 套件 | 数量 | 目标库 | 怎么跑 |
|------|------|--------|--------|
| 后端 pytest | **257** | `clipboard_test` | `cd server; python -m pytest` |
| Web 端（隔离模式，推荐） | **62** | `clipboard_web_test` | `.\scripts\run_web_tests.ps1` |
| Web 端（安全模式） | **62** | 当前后端所连的库 | `cd web; pnpm test` |

- **两套测试各用一个库**，可任意并行（后端 pytest 每用例 `drop_all` 重建表，
  共用库时并行会互相删表——实测踩过）
- **安全模式**不会删除任何既有数据：目标库名不含 `test` 时，破坏性操作被自动跳过
- **隔离模式**自动建库、起独立后端、跑完停掉；破坏性用例在其中照常覆盖

后端覆盖：`crud/clipboard.py` 纯函数（时区回退、标题换算、哈希、预览截断）、
`core/security.py`（哈希、JWT 及伪造/篡改/alg=none 降级攻击）、
`core/single_worker.py` 与 `core/logging_utils.py`、
auth 与 clipboard 接口（含**跨用户越权隔离**、去重契约、分页校验）、
后台管理（**普通用户 403、禁用/重置后旧令牌失效、WS 禁用校验、审计失败回滚**）。

**后端日志（2026-11-04）**：统一走 `app/core/logging_config.py`，默认写
`server/logs/app.log`（`RotatingFileHandler`，10MB × 5 份，UTF-8），
`LOG_LEVEL` / `LOG_FILE` / `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` / `LOG_CONSOLE` 可调；
uvicorn 的 access/error 日志也追加进同一文件，WS token 落盘前脱敏（`token=***`）。
补齐的事件：WS 连接/断开/鉴权失败、登录成功/失败、注册成功、广播失败。

**P1 日志加固（2026-11-05）**：剪贴板创建/更新/删除/清空补审计日志（只记
`user/item/字节数/送达数`，不记正文）；WS 失效连接被摘除时记 warning；
登录用户名做转义与长度限制（防日志注入/刷屏）；访问日志同时脱敏 `search=`。

**P2 日志加固（2026-11-05）**：每行日志带 `request_id`（`X-Request-ID` 回写响应头，
上游合法值沿用）；时间戳改为「毫秒 + 时区偏移」；脱敏覆盖 root 与纯终端模式；
统一异常入口（5xx 兜底堆栈、401 原因、会话回滚 DEBUG 轨迹）；`/dev/reset` 记审计；
Web 端新增 `utils/logger.ts`（开发 `debug`、生产 `warn`，可用 `VITE_LOG_LEVEL` 覆盖），
接入 401 自动登出、WS 连接日志与列表加载失败。

- 踩坑：**uvicorn 只配置 `uvicorn*` logger，不动 root**。root 没有 handler 且级别是
  WARNING，业务代码 `logger.info` 会被静默丢弃（实测 WS 连上了日志里什么都没有）；
  启动日志原先用 `print()`，stdout 被重定向时还有块缓冲，日志迟迟不落盘。
- 注意：`RotatingFileHandler` 不能多进程写同一文件，`run_web_tests.ps1` 的隔离后端
  已把 `LOG_FILE` 指到 `%TEMP%`。
- 文件不可写时自动退回终端（记 warning），不阻断启动。⚠️ `dictConfig` 会把打不开
  文件的 `PermissionError` 包成 `ValueError`，只捕 `OSError` 会漏掉这条降级路径。

**鸿蒙端（暂停上架）**：见 [`harmony/README.md`](../harmony/README.md)。
编译与打包已验证；安装运行、联调、`READ_PASTEBOARD` 授权未验证，恢复上架时再补做。

---

## 移动端 Web 适配（2026-11-01）

- **决策**：移动端不再依赖鸿蒙 App 上架，复用同一个 Web SPA；不拆移动端工程，
  store / composables / api 不感知设备。
- **布局**：桌面两栏；`≤900px` 单栏 + 顶部「历史记录 / 剪贴板输入」页签，默认「历史记录」。
  两个面板始终挂载，页签只切换 CSS 显示；保存成功后不自动跳页。
- **剪贴板**：不做后台监听，也不提供「同步剪贴板」按钮；用户直接在输入框粘贴/输入后保存。
  系统剪贴板读取不是 Web 端功能，iOS / 微信 WebView 的读取限制不再影响主流程。
- **范围**：本期只做响应式，不引入 PWA；不专门适配平板（768px 竖屏按移动单栏显示）。
- **验证**：`vue-tsc`、`vite build` 通过；隔离库 `clipboard_web_test` 全量 **55** 项通过（2026-11-01）。
- **未验证**：真机视觉、安全区、iOS / Android / 鸿蒙浏览器与微信 WebView 的布局与复制写回。

---

## 踩坑记录（永久保留，勿删）

### 第 7 步（鸿蒙 App，暂停上架）

1. **打包阶段报 `spawn java ENOENT`（错误码 00308018）不是签名问题，是缺 `JAVA_HOME`。**
   hvigor 的 `PackageHap` 需要 Java；报错文案指向"签名配置"极具误导性。
   指向 DevEco 自带 JBR 即可：`C:\Program Files\Huawei\DevEco Studio\jbr`。
   已封装进 `harmony/build.ps1`，它同时设置 `DEVECO_SDK_HOME` / `NODE_HOME` / `JAVA_HOME`。
2. **ArkTS 不允许无类型的对象字面量**（`arkts-no-untyped-obj-literals`）。
   给函数传 `{ username: x }` 这类匿名字面量**编译不过**，必须为每个请求体
   声明显式 `interface` 再传变量。空响应体的 `{}` 也一样，需要一个占位接口。
3. **`abilityAccessCtrl.checkAccessToken` 返回 `Promise`**，同步判断要用
   `checkAccessTokenSync`。用错会得到"类型无重叠"的编译错误。
4. **`.hvigor/` 不默认被忽略**：它是构建缓存与日志目录，每次构建都重写。
   已加入 `.gitignore`（连同 `oh_modules/`、`.idea/` 与 `*.p12`/`*.p7b`/`*.cer`）。
5. **设备上的 `127.0.0.1` 指向设备自身**，不是开发机。真机联调必须：
   改 `harmony/.../common/Config.ets` 的后端地址为电脑局域网 IP，
   并让后端 `--host 0.0.0.0` 启动（当前只监听 `127.0.0.1`，设备连不上）。
6. **自动保存的"是否有改动"必须用与保存时相同的归一化比较**：
   `saveEdits` 送出的是 `trim()` 后的值，若 `hasUnsavedChanges` 比较原始值，
   用户输入带尾随空格时会被永远判成"未保存" → **每 2 秒保存一次、无限循环**。
   `loadForEdit` 记录已保存内容时同样要 trim。
7. **自动保存失败后不要自动重试**：否则服务端不可用时会每 2 秒重试一次、无限刷屏。
   失败只提示，等用户继续输入或手动点「保存」。
8. **保存期间的新输入会漏掉计时**：`saving=true` 时 `@Watch` 被跳过，
   保存成功后要补一次「是否还有未保存改动」的检查，否则那段时间打的字永不自动保存。
9. **整卡可点击时，按钮必须放在可点区域之外**：只让「标题 + 内容」可点，
   操作按钮留在同级 Row 里——避免点「复制」也跳转。
10. **自动保存不要依赖 `@Watch` 装饰器**：上一版用 `@Watch('onDraftChanged')` 监听
    输入框状态，实测**倒计时根本没启动，而且不报任何错**（表现为"自动保存没生效"）。
    现改为在 `onChange` 回调里**显式调用** `scheduleAutoSave()`——只要输入事件到了，
    就一定安排上了，是确定性的。
11. **`saving` 标志必须在 `finally` 里复位**：一旦它卡在 `true`，
    `scheduleAutoSave` 会永久提前返回，自动保存此后静默失效（同样是"没触发"）。
12. **列表页与编辑页要分开**：编辑页有自己的输入状态与倒计时，混在列表页里时
    列表刷新、剪贴板监听、搜索都会干扰同一份状态。现为
    `pages/ClipboardPage`（浏览）+ `pages/EditPage`（编辑），路由常量集中在
    `common/Routes.ets`。
13. **`aboutToAppear` 里订阅是不够的**：页面被 `pushUrl` 覆盖时若触发了
    `aboutToDisappear`，监听会被退订；而返回时 `aboutToAppear` **不会**再执行，
    列表就永远收不到更新（表现为"从编辑页返回后列表还是旧的"）。
    订阅要抽成幂等方法，在 `aboutToAppear` 与 `onPageShow` 都调用一次。
14. **保存失败不要放行返回**：编辑页的「返回」若先保存再跳转，
    失败时必须停在本页提示错误，否则一返回刚编辑的内容就丢了。
15. **`ForEach` 的 key 不能只用 `item.id`**：刷新后同一个 id 的记录内容变了
    （例如改了标题），ArkUI 会按 key 复用旧组件而**不重绘**——数据是新的，
    界面却停在旧标题上。key 里必须带上会变的字段（这里用
    `${item.id}_${item.updated_at}`）。
16. **`onPageShow` 里不要发网络请求**：DevEco 预览器里 `onPageShow` 会**高频反复触发**，
    实测后端出现 **12,000+ 次、稳定 1 次/秒**的 `GET /items` 请求风暴
    （用 `netstat` 定位到请求方是 `Previewer` 进程，不是浏览器）。
    现在 `onPageShow` 只做**幂等重订阅**（有 `subscribed` 标志），不发请求；
    列表新鲜度由「保存后 store 通知」与「WebSocket 事件」保证，另有「刷新」按钮兜底。
17. **`http.RequestMethod.PATCH` 是 API 26 才新增的枚举成员，而本项目
    `compatibleSdkVersion` 是 5.0.0(12)。** 直接引用它**只会编译告警**，
    但在 API 12 真机上运行时取到的是 `undefined`，表现为「更新记录 / 自动保存」失败
    （新建不受影响，因为用的是 POST）。已改为字符串断言常量
    `'PATCH' as http.RequestMethod`（底层实现接受字符串），构建告警消失。

### 第 3 步

1. **`alembic.ini` 必须保持纯 ASCII**：Windows 上 configparser 按 locale（GBK）读取，
   中文注释会让 Alembic 直接崩溃。运行迁移建议带 `$env:PYTHONUTF8='1'`。
2. **autogenerate 会把开发库里手工建过的测试表当成"已删除的表"**写进迁移
   （曾生成 `op.drop_table('rt')`），在干净库上必然失败。
   **流程要求：生成迁移后逐行检查内容。**

### 第 8 步（补后端测试）

1. **`tests/conftest.py` 的 `engine` 夹具原本是 session 级，跑不起来。**
   pytest-asyncio 默认**每个测试用新的事件循环**，而引擎的连接池会把连接绑定在创建它的
   循环上 → 第二个测试起就报 `RuntimeError: got Future attached to a different loop`，
   表现为 `cannot rollback; the transaction is in error state`。
   已改为**函数级引擎**（每个测试建表一次，耗时约 28s / 150 项，可接受）。
   ⚠️ 不要"优化"回 session 级，除非同时把事件循环也提成 session 级。
2. **测单 worker 守卫时不能直接用 `LOCK_PORT`**：本地后端启动时会占着它，
   测试会被判成"已有实例"。夹具用 monkeypatch 换成临时空闲端口
   （为此 `lock_single_worker(port=None)` 改为在函数体内读模块常量，
   因为默认参数在定义时就求值，patch 不生效）。
3. **测试里不要用短密钥签 JWT**（如 `"attacker-secret"`）：会触发 PyJWT 的
   `InsecureKeyLengthWarning`，把测试输出搞脏。用 ≥32 字节的密钥。

### 第 8 步（测试隔离，P2）

1. **只改 `VITE_API_BASE_URL` 会让 HTTP 与 WebSocket 指向不同后端。**
   `useWebSocket` 原本只认 `VITE_WS_URL`，未配置时用**写死的** `ws://127.0.0.1:8000`。
   隔离测试把 HTTP 指向 8001 后，WS 仍连 8000，表现为"数据写进去了但收不到实时事件"
   （WebSocket 套件因此失败）。
   已改为**未配 `VITE_WS_URL` 时从 `API_BASE_URL` 推导**（`http→ws`）——
   只配一个地址即可，同时保留 `VITE_WS_URL` 覆盖能力（WS 与 API 不同主机时用）。
2. **测试账号会无限累积**：WebSocket 套件原用 `ws_e2e_<时间戳>` 每次运行注册新账号，
   实测开发库里积压了 **12 个**。改为固定账号 + "注册返回 409 则改登录"。
3. **`CLIPBOARD_LOCK_PORT` 让第二个合法实例可与开发实例并存**：
   单 worker 守卫靠独占固定端口实现，测试后端要另起实例就得换锁端口。
   这不是绕过守卫——同一实例内的多 worker 共用同一锁端口，照样被拦下。
4. **后端 pytest 与 Web 测试必须用不同的库**：pytest 每个用例都 `drop_all` 重建表，
   共用库时并行跑会互相删表。为此专门建了 `clipboard_web_test`
   （`server/scripts/ensure_database.py` 负责按需建库，幂等）。

### 第 2 步（Web 界面体验）

1. **`pending` 的判断依据错了**：原先用 `lastSaved === null`，于是**首次保存成功后
   再编辑，状态会一直显示旧的「已自动保存」时间**，永远回不到「待保存」。
   应按「内容签名是否等于已保存签名」判断，并把 `pending` 作为独立状态暴露。
2. **倒计时不能只写静态文案**：原状态栏写死「2 秒后自动保存」且不递减，
   用户无法判断是否真在倒计时。须由 composable 暴露 `remainingMs`/`progress` 驱动。
3. **`.notice` 不能复用到面板内联错误上**：`.notice` 是**固定悬浮**的全局 toast，
   用在内联位置会让错误飘到屏幕底部。内联错误请用 `.inline-error`。
4. **改内容要防唯一约束冲突**：`(user_id, content_hash)` 有唯一约束，而
   `update_item` 原先把 `content_hash` 直接改掉——改成与另一条相同时会在 commit
   抛 `IntegrityError`（表现为 500）。已提前查重并返回 `409`。
   ⚠️ 支持「点列表载入编辑」后这条路径**极易触发**，不要移除查重。
5. **`uploadText` 的更新分支也需要 404 回退**：`saveDraft` 有"记录被删则改为新建"的
   兜底，`uploadText` 原先没有——载入编辑的记录被删后再保存会直接抛 404。
6. **载入编辑必须分两步**（`requestEdit` → `applyRequestedEdit`）：
   载入会切换 `draftId`，而输入框里可能还有没到自动保存时机的改动。
   让输入区**先落盘、再切换**，否则那几个字会跟着旧草稿一起丢。
7. **列表排序必须显式传 `sort_by=updated_at`**：后端默认是 `created_at`，
   而产品要的是"最近修改在前"。漏传的表现是**编辑了旧记录却不上移**，
   用户会以为没保存成功（这个困惑真的发生过）。
   两个客户端都改了；`web/tests/e2e.test.ts` 有回归用例，且已验证
   把 `sort_by` 改回 `created_at` 时该用例**确实会失败**。
8. **`hasUnsaved` 不能收参数、更不能传"签名"进去**：它内部会 `signature(value)`，
   若调用方传入的已经是签名（例如 watcher 的 `current`），签名就被套了两层
   （`内容\0标题\0标题`），与 `savedSignature` **永不相等** → 永远判定为"有改动"。
   表现：**点开一条记录不做任何修改，2 秒后也会自动保存一次**。
   已改成无参的 `hasUnsavedChanges()`，直接用 `text.value` 算签名，杜绝传错。
   `web/tests/autosave.test.ts` 有回归用例，且已验证还原 bug 时它会失败。

### 第 4 步

1. **`passlib` 在 Python 3.13 上根本装不了**：PEP 594 移除了标准库 `crypt` 模块，
   而 passlib 依赖它，`import` 阶段即 `ModuleNotFoundError`。
   ⚠️ **pin 老版本 bcrypt 是死路**——根本走不到调用 bcrypt 那一步。
   改用 `pwdlib`；对应地 JWT 用 `PyJWT`（只需 HS256，不需要已停止维护的 `python-jose`）。
2. **`pwdlib` 的 `PasswordHash.recommended()` 只返回 Argon2**，本项目装的是
   `pwdlib[bcrypt]`，调它会抛 `HasherNotAvailable`。必须显式
   `PasswordHash((BcryptHasher(rounds=12),))`。
3. **bcrypt 限制的是 72 字节，不是 72 字符**。只写 `max_length=72`（字符）会让
   25 个汉字通过校验后在哈希阶段抛错变成 500。已按 UTF-8 字节数校验。
4. **`JWT_SECRET` 短于 32 字节会让 PyJWT 发 `InsecureKeyLengthWarning`**
   （RFC 7518 3.2），故开发默认值也保持 32 字节以上。
5. Web 端两个易错点：`AuthResponse` 是扁平结构（用户对象在 `token.user` 上，不是整个响应）；
   401 拦截器**必须排除 `/auth/login` 与 `/auth/register` 自身**，否则登录页输错一次密码
   就触发全局登出。
6. **顶部提示必须有生命周期**：它只在被下一条提示覆盖时才变，而登出后界面停在登录页、
   没有任何操作能覆盖它 —— 导致"已退出登录"永久残留（错误提示同理）。
   已抽成 `web/src/composables/useNotice.ts`。

### 第 5 步

1. **单 worker 守卫只查环境变量是无效的。** uvicorn 的 CLI `--workers N`
   **不会**写进环境变量（实测 worker 进程里 `WEB_CONCURRENCY` 是 `None`），
   只有 `WEB_CONCURRENCY=N` 这条路径才会 → 必须额外做"独占固定回环端口"检测。
   ⚠️ 锁端口**必须固定**：实测 `bind(('127.0.0.1', 0))` 每次都返回不同端口
   （连续三次 13099/13100/13101），"探测空闲端口再绑定"的写法在并发下**永不相撞**。
2. **日志脱敏不能用 `logging.Filter` 改写 `record.args`。** uvicorn 的 `AccessFormatter`
   要求 args 里恰好 5 个字段，清空后**每个 HTTP 请求**都抛 `ValueError`，
   访问日志整体报废。正确做法：`scrub_scope_token()` 从 ASGI scope 删掉 token
   （日志里根本没有它），再包一层 formatter 兜底。
   ⚠️ 不要把 `?token=***` 拼回 `scope["path"]`，会被百分号编码成 `%3Ftoken%3D...`。
3. **Node 测试运行器会并行跑多个测试文件**：两个套件共用同一账号时，
   一方的增删会让另一方的 `total` 断言随机失败（实测期望 5、实际 6）。
   各套件必须用**独立账号**。
4. **`pnpm test -- <file>` 不会只跑指定文件**：`--` 之后的参数被追加到已有 glob 之后。
   要单跑得直接调 node：`node --experimental-strip-types --test tests/websocket.test.ts`
5. 去重的两条易错契约（第 6 步）：命中时**只刷新 `updated_at`、不改 `created_at`**，
   且**未显式传 `title` 时不得覆盖原标题**。

---

## 已知问题与技术债

### ✅ P2 · 测试清库风险（已解决）

破坏性用例会清空数据。此前的问题是：`E2E_ALLOW_DESTRUCTIVE` 只保护了清空**用例**，
而**收尾钩子里的 `dev/reset` 是无条件调用的**——它对开发库是删数据操作，
于是"跑一次测试"就会清掉 demo 用户的全部记录。

**修复分三层**（缺一层都不够）：

1. **安全守卫（最重要）**：测试先调 `GET /api/v1/dev/db` 探测目标库，
   **只有库名含 `test` 且显式设了 `E2E_ALLOW_DESTRUCTIVE=1` 才允许破坏性操作**。
   探测失败（dev 路由未开启/后端不可达）一律按"非测试库"处理（fail-safe）。
   于是即使误对开发库跑测试并打开了开关，也不会删数据。
2. **隔离运行脚本** `scripts/run_web_tests.ps1`：自动建库（`clipboard_web_test`）、
   起一个独立后端（端口 8001、独立锁端口），跑完停掉。破坏性用例在测试库上照常覆盖。
3. **测试账号不再累积**：WebSocket 套件原用带时间戳的用户名，每次运行都新建账号
   （实测开发库里积压了 **12 个**）。改为固定账号 + "能注册就注册、已存在就登录"。

后端测试本就打 `clipboard_test`（`tests/conftest.py`），无需改动。

> **三个库各司其职**：`clipboard`（开发，人工使用）、`clipboard_test`（后端 pytest）、
> `clipboard_web_test`（Web 隔离测试）。分开是因为 pytest 每个用例都会 `drop_all`
> 重建表——共用库时并行跑会互相删表（实测踩过：Web 测试因表被删而失败）。
>
> ⚠️ **库名必须含 `test`**：安全守卫以此判定"这是可丢弃的测试库"。
> 名字不含 `test` 的库**不允许**跑破坏性用例（本脚本自己也会二次确认）——
> 曾把库命名为 `clipboard_e2e`，结果被守卫正确拦下。

### ✅ 并发编辑体验改进（低成本，已完成）

当前保存仍是**后写覆盖**（没有版本号/乐观锁），但已补两处低成本提示：

1. **进入编辑前重取最新**（Web）：点历史记录时先 `GET /items/{id}` 拿详情，
   而不是用列表里几秒前的快照——否则别处刚改过的内容会被本地编辑静默覆盖。
   鸿蒙编辑页本就在 `loadExisting` 里按 id 重取。
2. **正在编辑的记录被别处更新时提示**：两端在 `clipboard.updated` 命中当前编辑
   记录（且内容与已保存/在途内容不同）时显示警示横幅，提供「载入最新」与「忽略」。
   服务端保存成功后也会广播同一条事件，因此用 `inFlightContent` 排除自己的回显，
   避免误报。

**仍待解决**：服务端没有 `version` 字段与 `expected_version` 校验，「忽略」后保存
仍会覆盖对方内容。要做真正的冲突检测需加乐观锁（条件
`UPDATE ... WHERE version = :expected`，冲突返回 409/412，客户端提供
重新载入 / 覆盖 / 另存为）。

### ✅ 已关闭

- **P1 / P4 / P7 / P8**：`DEBUG` 与开发路由解耦、文档文件名统一、`.gitignore` 补 `dist/`、
  README 路由表口径 —— 过程见 git log
- **P3 多 worker 打破广播**：已决策**强制单 worker**并落地运行时守卫
  （见「第 5 步踩坑记录」1 与 [`ws-protocol.md`](ws-protocol.md)）。
  解除限制的前置条件是先引入 Redis Pub/Sub
- **P5 认证依赖兼容性**：见「第 4 步踩坑记录」1；顺带装了 `httpx`（第 8 步也要用）
- **P6 WS token 日志泄露**：见「第 5 步踩坑记录」2

---

## 本地基础设施

**Postgres 16 走 Docker 容器（宿主 5433）**；本机原生的 PostgreSQL 18 保留不动（占 5432）。
连接串、数据卷、健康检查等见 `infra/docker-compose.yml` 顶部注释与
`scripts/verify_postgres.py`。

- **Docker Hub 已恢复可拉取**（2026-11-08 实测 `python:3.13-slim`、`node:24-alpine`、
  `nginx:alpine` 均成功）；网络不稳时仍建议预拉取或改用镜像源
- Docker CLI 需访问命名管道，**受限沙箱下会被拒绝**，故 docker 命令都需完全权限
- 本地与生产**均为 16**，避免跨大版本 `pg_dump/pg_restore` 不兼容

## 环境前置条件

| 组件 | 状态 | 说明 |
|------|------|------|
| Python 3.13.7 | ✅ | `server/venv` 已建 |
| Node 24.11.1 + pnpm | ✅ | `web/node_modules` 已装；本地 pnpm 10.13.1，构建镜像内固定 11.7.0 |
| Docker Desktop | ✅ | CLI 需完全权限才能访问命名管道 |
| Docker Hub 拉取 | ✅ | 已恢复（2026-11-08）；网络不稳时用镜像源或预拉取 |
| 本机 PostgreSQL 18 | ✅ `5432` | **保留不动**，与容器并存 |
| 容器 PostgreSQL 16 | ✅ healthy | 本地开发主用（宿主 5433） |
| Redis | ⬜ 空闲 | **本阶段不引入**（P3 走单 worker）；需跨进程广播时再启用 |
| MinIO | ⚠️ | 9000 被 Windows 保留段占用，阶段二需换端口 |

### Windows 保留端口段（重要）

```
1034-1133, 4881-4980, 5141-5240, 8903-9002, 50000-50059
```

**5141-5240** 覆盖了原定的 Vite 5173 → 已改用 **5273**；**8903-9002** 覆盖 MinIO 的 9000。
排查命令：`netsh int ipv4 show excludedportrange protocol=tcp`

---

## 下一步行动

### 后台管理页（已实现，待部署）

- **实现范围**：同站 `/admin`、用户/剪贴板/邀请码管理、概览统计、操作审计；
  禁用优先 + 物理删除；应用日志 + `admin_audit_logs` 双审计。
- **安全 P0 已落地**：WS 禁用即断开、`token_version` 令牌撤销、
  高危操作审计同事务、管理端不落盘密码、管理员令牌 12 小时。
- **验证（2026-11-10）**：后端 257 项、Web 62 项通过；`typecheck` / `build` 通过；
  浏览器验证概览、用户、剪贴板、邀请码、操作日志均正常。
- **管理员初始化**：`scripts.set_admin` 支持 `--create`，一条命令建号 + 授权（密码交互输入）。
- **界面要点**：概览卡片可跳转；筛选条单行；剪贴板详情与邀请码使用详情用模态框；
  分页默认 10 条；邀请码生成需填写最大使用次数，明文只显示一次。
- **设计与步骤**：见 [`admin.md`](admin.md)。
- **待部署**：迁移 `0003` + `0004` → 重建镜像 → `scripts.set_admin` → 按 admin.md §8.3 启用 IP 白名单/VPN。
- **未纳入本轮（P1）**：CSP、最后管理员保护、管理员间提权限制、明文查看审计、
  422 密码回显脱敏、管理 API 限流。

### v1.0.0 发版收尾（仅文字剪贴板）

1. **Web 端人工验收**：桌面 + 手机覆盖保存、列表、复制、自动保存、搜索/排序/分页
   与多标签同步；真机布局、安全区与复制仍需人工确认。
2. **生产部署收尾**：域名 + ICP 备案 + 正式证书。
   当前已用自签证书上线（`43.134.121.173:8443`，方案 B），见
   [`deployment.md`](deployment.md)。
3. **打 tag 发布**：版本号已统一为 `1.0.0`，待确认发布渠道后打 tag。

> 鸿蒙 App 已暂停上架，不再列入 v1.0.0 发版必做项；恢复时见
> [`harmony/README.md`](../harmony/README.md)。

### v1.1（下一版本）

- 图片剪贴板 + 对象存储（原阶段二）
- 文件剪贴板 + 体验优化（原阶段三）
- 对象存储先做**适配层**：MinIO 端口 9000 被 Windows 保留段占用，需换端口；
  开发期也可先用本地磁盘实现，接口保持 S3 兼容，后续切换不改业务代码

### 之后可考虑

- CI（`.github/workflows/`）、LICENSE、GitHub 默认分支设置
- 清理测试账号（一般不需要——现在每次运行只用一个固定账号）：
  `DELETE FROM users WHERE username = 'ws_e2e_account';`
