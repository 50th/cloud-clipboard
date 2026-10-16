# web —— 云剪贴板 Web 端

**Vue 3 + TypeScript + Vite + Pinia**。

启动步骤见仓库根 [`README.md`](../README.md)；规范与契约见 [`../AGENTS.md`](../AGENTS.md)。

## 界面结构

`App.vue` 是唯一页面：**未登录时显示登录/注册**（`LoginPanel.vue`），登录后是左右两栏。

- **左栏 · 历史记录**（`ClipboardHistory.vue`）：搜索框、刷新、排序、清空全部 + 列表（独立滚动）。
  **历史相关操作全部集中在左栏。**
- **右栏 · 剪贴板输入**（`InputPanel.vue`）：标题、加高正文编辑区（最小 240px）、
  上传 / 同步剪贴板 / ＋新建剪贴板 / 清空输入，以及自动保存开关与状态。

每条记录（`ClipboardItemCard.vue`）：标题、相对时间、正文（超长折叠）、复制 / 删除。
顶部还显示**实时连接状态**（WebSocket 是否在线）。

## 标题与自动保存

**标题**：用户填写则原样保存；留空由服务端生成 `<用户名> · <月-日 时:分>`，
时间按前端自动传的浏览器时区显示，如 `demo · 10-05 22:26`。
**去重命中时不覆盖已有标题**；搜索同时匹配标题与正文。

**自动保存**（`composables/useAutoSave.ts`）：默认开启，**停止输入 2 秒**后保存。
它**复用同一条"草稿"记录**（store 的 `saveDraft`）——打字过程中反复保存只更新那一行，
不会每个中间态都新建一行。

**什么时候才会新开一条记录**（重要）：

| 操作 | 行为 |
|------|------|
| 继续输入 / 修改内容 | 更新**同一条**草稿 |
| 点「清空输入」 | 只清空界面，**仍更新同一条** |
| 点「＋ 新建剪贴板」 | **解除草稿关联**，之后输入另起一条 |
| 点「上传」且内容与草稿不同 | 另起一条记录 |
| 点「清空全部」 | 删除所有记录并解除关联 |

> 设计意图：**只有显式点「新建剪贴板」才新开记录**，避免"清空 → 重新输入"意外多出一行。
> `Ctrl+Enter` 可快速上传。

## 手工验证

1. 在任意地方复制一段文字（Ctrl+C）
2. 点右栏 **「同步剪贴板」**（读取必须由点击手势触发，浏览器不允许后台自动读）
3. 左栏出现新记录，提示「已同步剪贴板」
4. 再复制**相同内容**并同步 → 不新增记录，提示「内容已存在，已刷新时间戳」
5. 点记录的 **「复制」** → 变为「✓ 已复制」，去别处 Ctrl+V 验证
6. **开两个标签页**，在 A 里上传 → B 应自动出现该记录

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

- `e2e.test.ts`：真实 store + 真实后端。含登录/401、列表、上传、去重契约（标题与时间戳）、
  搜索、排序、删除、清空，以及**安全守卫的回归用例**
- `websocket.test.ts`：真实 `useWebSocket`，验证「A 上传 → B 出现」「A 删除 → B 消失」、
  去重也会广播、WS 地址跟随 API 地址，以及令牌无效时 4401 不重连
- `notice.test.ts`：纯前端，覆盖顶部提示必须**自动消失**

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
> **剪贴板读写依赖浏览器 API，不在自动化范围内**，需按上一节手工验证。

## 目录结构

```
web/
├── vite.config.ts               # 插件、@ 别名、端口 5273
├── package.json                 # imports: #src/* → ./src/*
├── pnpm-workspace.yaml          # allowBuilds 放行 esbuild / vue-demi
├── scripts/generate-api-types.mjs
├── tests/                       # e2e / websocket / notice（见上）
└── src/
    ├── main.ts                  # 挂载应用 + Pinia + 401 登出回调
    ├── App.vue                  # 登录门禁 + 两栏布局 + 实时连接状态
    ├── api/client.ts            # axios 封装 + token 拦截器 + 401 处理 + 错误归一化
    ├── types/api.d.ts           # 由 openapi-typescript 生成，勿手改
    ├── utils/clipboard.ts       # 剪贴板读写（自身写入标志 + execCommand 降级）
    ├── stores/
    │   ├── clipboardStore.ts    # 列表、分页、上传、去重识别、实时事件处理
    │   └── userStore.ts         # 登录 / 注册 / 会话恢复
    ├── composables/
    │   ├── useClipboard.ts      # 读剪贴板 → 上传 的编排
    │   ├── useCopy.ts           # 复制回剪贴板 + 「已复制」状态
    │   ├── useAutoSave.ts       # 防抖自动保存
    │   ├── useNotice.ts         # 顶部提示的生命周期（自动消失）
    │   └── useWebSocket.ts      # 实时同步：心跳、退避重连、事件分发
    └── components/
        ├── LoginPanel.vue       # 登录 / 注册
        ├── ClipboardHistory.vue # 左栏
        ├── ClipboardItemCard.vue
        └── InputPanel.vue       # 右栏
```

## 导入别名（两套并存，各有原因）

| 别名 | 解析方式 | 用在哪 |
|------|----------|--------|
| `@/*` | Vite `resolve.alias` + tsconfig `paths` | 所有 `.vue` 组件、`main.ts` |
| `#src/*` | `package.json` 的 `imports` 字段 | store / composables / api / utils |

**为什么不全用一套**：Node 直接运行时**不读 tsconfig `paths`**，`@/xxx` 会被当成裸包名报
`ERR_MODULE_NOT_FOUND`；而 `#src/*` 走 `package.json` 的 `imports`，Node 原生支持，
测试才能直接跑源码。所以**被测试引入的模块必须用 `#src/*` 且带 `.ts` 扩展名**
（Node ESM 要求显式扩展名）。

改动这些模块时别把 `#src/` 换成 `@/`，否则 `pnpm test` 报模块找不到。
