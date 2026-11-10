# web —— 云剪贴板 Web 端

**Vue 3 + TypeScript + Vite + Pinia**。

启动步骤见仓库根 [`README.md`](../README.md)；规范与契约见 [`../AGENTS.md`](../AGENTS.md)。

## 界面结构

`App.vue` 是唯一页面：**未登录时显示登录/注册**（`LoginPanel.vue`）。
登录后桌面端为左右两栏，移动端为顶部页签单栏。

- **历史记录**（`ClipboardHistory.vue`，桌面左栏 / 移动「历史记录」页）：
  搜索框、刷新、排序、清空全部 + 列表。
- **剪贴板输入**（`InputPanel.vue`，桌面右栏 / 移动「剪贴板输入」页）：
  标题、加高正文编辑区（最小 240px）、保存 / ＋新建剪贴板 / 清空正文，
  以及自动保存开关与状态。

每条记录（`ClipboardItemCard.vue`）：标题、相对时间、正文（超长折叠）、复制 / 删除。
顶部还显示**实时连接状态**（WebSocket 是否在线）。

### 桌面 / 移动端统一布局（≤900px）

桌面端两栏同时可见；移动端在 `<App.vue>` 顶部显示「历史记录 / 剪贴板输入」两个页签，
一次只显示一栏，**默认停在「历史记录」**。两个面板始终挂载，页签切换只是 CSS 显示/隐藏，
所以：

- 输入区的草稿、自动保存倒计时不会因切页而丢；
- 历史列表的分页、搜索、滚动位置保持不变；
- 操作语义两端完全一致：点记录 → 载入输入区编辑；复制 / 删除仍是卡片上的按钮；
  保存行为不变。

移动端额外做两点适配：

1. **点历史记录会自动切到「剪贴板输入」页签**（桌面两栏都可见，状态切换无副作用）。
2. **保存成功后停留在当前页，不自动跳转**；历史页签的计数会自行更新，
   需要看结果时点一下「历史记录」即可。

Web 端不提供「同步剪贴板」按钮：读取系统剪贴板在移动浏览器上限制多（HTTPS、
用户手势、iOS 系统粘贴确认、WebView 禁用），因此统一改为**用户手动粘贴/输入后保存**。

页签只在移动端显示；桌面端布局与操作保持不变。文案统一使用「输入区」，
不再出现「右侧输入框」这类只适合桌面的描述。移动端没有独立工程，复用同一套组件、
store、composables 与 API 封装。

### 后台管理（`/admin`）

同一构建产物按路径分发：用户端在 `/`，管理端在 `/admin`。管理端是独立入口
（`src/admin/main.ts` + 独立 Pinia），**不使用 vue-router**，用 store 内的视图状态切换；
令牌只存 `sessionStorage`，不保存密码。页面包括：概览、用户管理、用户详情、
剪贴板管理、邀请码、操作日志。设计、接口与权限说明见 [`../docs/admin.md`](../docs/admin.md)。

**列表默认按「修改时间」倒序**（下拉框可切「最近修改 / 最早修改」）：
编辑过的记录会立刻上移。注意后端 `sort_by` 默认是 `created_at`，
所以 `clipboardStore.fetchItems` **必须显式传 `sort_by: 'updated_at'`**——不传的话
编辑一条旧记录后它不会上移，看起来像"没保存成功"（`tests/e2e.test.ts` 有回归用例）。

## 标题与自动保存

**标题**：用户填写则原样保存；留空由服务端生成 `<用户名> · <月-日 时:分>`，
时间按前端自动传的浏览器时区显示，如 `demo · 10-05 22:26`。
**去重命中时不覆盖已有标题**；搜索同时匹配标题与正文。

**自动保存**（`composables/useAutoSave.ts`）：默认开启，**停止输入 2 秒**后保存，
右下角显示**真实递减的倒计时**与进度条（不是静态文案），也可点「立即保存」跳过等待。
它**复用同一条"草稿"记录**（store 的 `saveDraft`）——打字过程中反复保存只更新那一行，
不会每个中间态都新建一行。

**点历史记录可载入输入区编辑**：条目本身可点击（也支持 Enter/空格），
载入后输入区顶部显示「正在编辑已有记录」，此时保存**更新那一条**，不会新建。
想新开一条，点输入区下方的「＋ 新建剪贴板」。

> 载入前会**先把当前未保存的内容落盘**，否则刚敲的几个字会跟着旧草稿一起丢
> （见 store 的 `requestEdit` / `applyRequestedEdit` 两步流程）。

**什么时候才会新开一条记录**（重要）：

| 操作 | 行为 |
|------|------|
| 继续输入 / 修改内容 | 更新**同一条**草稿 |
| 点「清空输入」 | 只清空正文、**保留标题**，仍更新同一条 |
| 点「＋ 新建剪贴板」 | **解除草稿关联**，之后输入另起一条 |
| 点历史记录载入后保存 | 更新**被点开的那一条**（即使内容改了） |
| 点「保存」且内容与草稿不同 | 另起一条记录（草稿模式下） |
| 点「清空全部」 | 删除所有记录并解除关联 |

> 设计意图：**只有显式点「新建剪贴板」才新开记录**，避免"清空 → 重新输入"意外多出一行。
> `Ctrl+Enter` 可快速保存。
>
> ⚠️ 把某条内容改成与**另一条**相同时，服务端返回 `409`（`(user_id, content_hash)`
> 唯一约束），界面会提示「已有另一条相同内容的记录」，原记录保持不变。

## 手工验证

**桌面端**：

1. 在任意地方复制一段文字（Ctrl+C）
2. 在输入区正文框里粘贴（Ctrl+V），点「保存」
3. 历史列表出现新记录，提示「已保存」
4. 再粘贴**相同内容**并保存 → 不新增记录，提示「内容已存在，已刷新时间戳」
5. 点记录的 **「复制」** → 变为「✓ 已复制」，去别处 Ctrl+V 验证
6. **开两个标签页**，在 A 里保存 → B 应自动出现该记录
7. 点历史记录某条 → 内容进入输入区并可编辑，保存后**仍是同一条**（列表不新增）

**移动端补充验证**（Chrome DevTools 切到 iPhone / Android 尺寸，或真机）：

8. 顶部出现「历史记录 / 剪贴板输入」页签，默认停在「历史记录」，输入栏隐藏。
9. 点某条记录 → 自动跳到「剪贴板输入」并载入该条。
10. 输入内容后点「保存」→ 仍停留在「剪贴板输入」，历史页签计数增加；
    点「历史记录」能看到刚保存的记录。

> ⚠️ 真机调试注意：`http://192.168.x.x` **不是安全上下文**，`navigator.clipboard`
> 不可用，历史记录的「复制」会走 `execCommand` 降级。Android 可先
> `adb reverse tcp:5273 tcp:5273`，再用 `http://localhost:5273`；iOS 需要 HTTPS 隧道
> 或正式域名。Vite 默认只监听 `127.0.0.1`，给手机访问需 `--host 0.0.0.0`，
> 但那样仍是 HTTP，只能验证布局、保存与实时同步。

## 日志

前端统一走 `src/utils/logger.ts`，**组件、store、composables 不直接调 `console.*`**：

- 级别：开发默认 `debug`，生产默认 `warn`；可用 `VITE_LOG_LEVEL=debug|info|warn|error` 覆盖
- 输出带 `[cloud-clipboard]` 前缀，附加参数（如异常对象）原样透传，方便在控制台展开
- 已接入：401 自动登出的原因、WebSocket 连接/重连记录、列表加载失败、清空失败、会话恢复失败
- ⚠️ 不要打印令牌或剪贴板正文：控制台截图与用户反馈里的日志片段都会外流

## 测试

```powershell
# 隔离模式（推荐）：自动起一个指向测试库的独立后端，跑完自动停。
# 破坏性用例（清空全部）会被覆盖，且绝不碰开发库。
.\scripts\run_web_tests.ps1

# 安全模式：打当前后端（默认 8000）。不会删除任何既有数据。
pnpm test
pnpm typecheck     # vue-tsc --noEmit
pnpm build         # 类型检查 + 构建
pnpm run gen:api   # 契约变更后重新生成 src/types/api.d.ts
```

`pnpm test` 用 Node 内置测试运行器 + 类型擦除**直接跑 `tests/**/*.test.ts`**：

- `e2e.test.ts`：真实 store + 真实后端。含登录/401、列表、保存、去重契约（标题与时间戳）、
  搜索、排序、删除、清空、**载入已有记录编辑**（改内容仍更新同一条、409 冲突、
  被删后回退新建），以及**安全守卫的回归用例**
- `websocket.test.ts`：真实 `useWebSocket`，验证「A 保存 → B 出现」「A 删除 → B 消失」、
  去重也会广播、WS 地址跟随 API 地址，以及令牌无效时 4401 不重连
- `autosave.test.ts`：纯前端。自动保存**倒计时**必须真实递减、到点保存一次、
  继续输入会重置、`markSaved`/关闭开关会取消，以及「保存过之后再编辑仍应显示待保存」
- `notice.test.ts`：纯前端，覆盖顶部提示必须**自动消失**
- `admin.test.ts`：管理端纯逻辑，`/admin` 路径判定与 `sessionStorage` 不可用时的内存兜底

### 安全守卫（重要）

破坏性操作（清空全部、`dev/reset`）**必须同时满足**两个条件才执行：

1. 目标库名含 `test`（启动时通过 `GET /api/v1/dev/db` 自动探测）
2. 显式设置 `E2E_ALLOW_DESTRUCTIVE=1`

探测失败（dev 路由未开启 / 后端不可达）一律按**非测试库**处理。
因此 `pnpm test` 打在开发库上是安全的：**即使误设了开关也不会删数据**。

### 其他注意

> ⚠️ Node 测试运行器**并行**跑各文件，所以各套件用**独立账号**——共用会让 `total`
> 断言随机失败（实测踩过）。WebSocket 套件用固定账号 `ws_e2e_account`，
> **不会**随运行次数增长；如需清理：`DELETE FROM users WHERE username = 'ws_e2e_account'`。
>
> ⚠️ **`pnpm test -- <file>` 不会只跑指定文件**（参数被追加到既有 glob 之后）。
> 要单跑得直接调 node：`node --experimental-strip-types --test tests/notice.test.ts`
>
> ⚠️ 未配置 `VITE_WS_URL` 时，WebSocket 地址**从 `VITE_API_BASE_URL` 推导**。
> 只改 API 地址即可；若 WS 与 API 不同主机（如走反向代理）才需要单独配 `VITE_WS_URL`。
>
> **复制写回依赖浏览器剪贴板 API，不在自动化范围内**；Web 端不读取系统剪贴板，
> 读取相关行为不需要验收。复制仍按上一节手工验证。

## 目录结构

```
web/
├── vite.config.ts               # 插件、@ 别名、端口 5273
├── package.json                 # imports: #src/* → ./src/*
├── pnpm-workspace.yaml          # allowBuilds 放行 esbuild / vue-demi
├── scripts/generate-api-types.mjs
├── tests/                       # e2e / websocket / autosave / notice / logger / admin
└── src/
    ├── main.ts                  # 按路径分发：/admin → admin/main，其余 → bootstrap
    ├── bootstrap.ts             # 用户端启动：Pinia + 401 登出回调 + 挂载 App.vue
    ├── App.vue                  # 登录门禁 + 桌面两栏 / 移动页签 + 实时连接状态
    ├── admin/                   # 管理端（独立入口、store、api、views、组件与样式）
    ├── api/client.ts            # axios 封装 + token 拦截器 + 401 处理 + 错误归一化
    ├── types/api.d.ts           # 由 openapi-typescript 生成，勿手改
    ├── utils/clipboard.ts       # 剪贴板写入（自身写入标志 + execCommand 降级）
    ├── stores/
    │   ├── clipboardStore.ts    # 列表、分页、保存、去重识别、实时事件处理
    │   └── userStore.ts         # 登录 / 注册 / 会话恢复
    ├── composables/
    │   ├── useClipboard.ts      # 系统剪贴板读取编排（当前未接入 UI）
    │   ├── useCopy.ts           # 复制回剪贴板 + 「已复制」状态
    │   ├── useAutoSave.ts       # 防抖自动保存
    │   ├── useNotice.ts         # 顶部提示的生命周期（自动消失）
    │   └── useWebSocket.ts      # 实时同步：心跳、退避重连、事件分发
    └── components/
        ├── LoginPanel.vue       # 登录 / 注册
        ├── ClipboardHistory.vue # 历史面板（桌面左栏 / 移动「历史记录」页）
        ├── ClipboardItemCard.vue
        └── InputPanel.vue       # 输入面板（桌面右栏 / 移动「剪贴板输入」页）
```

## 导入别名（两套并存，各有原因）

| 别名 | 解析方式 | 用在哪 |
|------|----------|--------|
| `@/*` | Vite `resolve.alias` + tsconfig `paths` | 所有 `.vue` 组件（含管理端）、`main.ts`、`bootstrap.ts` |
| `#src/*` | `package.json` 的 `imports` 字段 | store / composables / api / utils（用户端与管理端共用） |

**为什么不全用一套**：Node 直接运行时**不读 tsconfig `paths`**，`@/xxx` 会被当成裸包名报
`ERR_MODULE_NOT_FOUND`；而 `#src/*` 走 `package.json` 的 `imports`，Node 原生支持，
测试才能直接跑源码。所以**被测试引入的模块必须用 `#src/*` 且带 `.ts` 扩展名**
（Node ESM 要求显式扩展名）。

改动这些模块时别把 `#src/` 换成 `@/`，否则 `pnpm test` 报模块找不到。
