# web —— 云剪贴板 Web 端

**Vue 3 + TypeScript + Vite + Pinia**。当前处于 **第 2 步：Web 端骨架 + 单端闭环**（数据已持久化到 PostgreSQL）。

## 快速开始

前置：后端已运行（见 `../server/README.md`），数据库容器已启动。

```powershell
# 0. 启动数据库容器（仓库根目录）
docker compose -f infra/docker-compose.yml up -d

cd web

# 1. 环境变量
Copy-Item .env.example .env

# 2. 安装依赖
pnpm install

# 3. 从后端契约生成类型（需后端在 8000 端口运行）
pnpm run gen:api

# 4. 启动开发服务器
pnpm run dev
```

打开 <http://127.0.0.1:5273>。

> ⚠️ 必须用 `127.0.0.1` / `localhost` 访问。浏览器剪贴板 API **只在 HTTPS 或 localhost 下可用**；
> 端口固定 5273——**不能改回 5173**，它落在 Windows 保留段 5141-5240 内会无法绑定（见 `vite.config.ts` 注释）。

## 界面结构

左右两栏：

- **左栏 · 历史记录**（`ClipboardHistory.vue`）：搜索框（列表顶部）、刷新、排序、清空全部，以及记录列表。
  **历史相关操作全部集中在左栏**，列表区域独立滚动。
- **右栏 · 剪贴板输入**（`InputPanel.vue`）：标题输入、加高正文编辑区（最小 240px）、
  上传 / 同步剪贴板 / **＋ 新建剪贴板** / 清空输入，以及自动保存开关与状态。

每条记录（`ClipboardItemCard.vue`）显示：**标题**、相对时间、正文（超长折叠可展开）、复制 / 删除按钮。

## 标题与自动保存

**标题**：用户填写则原样保存；留空或只填空格 → 服务端生成 `<用户名> · <月-日 时:分>`，
**时间按 `timezone`（前端自动传浏览器时区）显示**，如 `demo · 10-05 22:26`。
命中内容去重时**不覆盖**已有标题。搜索同时匹配标题与正文。

**自动保存**（`composables/useAutoSave.ts`）：右栏默认开启，**停止输入 2 秒**后保存，可随时关闭。
右下角显示状态（等待输入 / N 秒后自动保存 / 保存中… / **✓ 已自动保存 hh:mm:ss**，成功显绿色）。

**自动保存复用同一条「草稿」记录**（store 的 `saveDraft`）：打字过程中反复保存只更新那一行，
**不会每个中间态都新建一行**。

**什么时候才会新开一条记录**（重要）：

| 操作 | 行为 |
|------|------|
| 继续输入 / 修改内容 | 更新**同一条**草稿 |
| 点**「清空输入」** | 只清空界面，**仍然更新同一条**——符合"继续编辑"的预期 |
| 点**「＋ 新建剪贴板」** | **解除草稿关联**，之后输入的内容另起一条记录 |
| 点「上传」且内容与草稿不同 | 另起一条记录 |
| 点「清空全部」 | 删除所有记录并解除关联 |

> 设计意图：**只有用户显式点「新建剪贴板」才会新开记录**，
> 避免"清空 → 重新输入"意外多出一行。清空输入后草稿仍绑定，是想让你继续编辑同一条。

`Ctrl+Enter` 可快速上传。

## 单端闭环手工验证

1. 在任意地方复制一段文字（Ctrl+C）
2. 点右栏 **「同步剪贴板」**（读取必须由点击手势触发，浏览器不允许后台自动读）
3. 左栏顶部出现新记录，提示「已同步剪贴板（新记录 …）」
4. 再复制一次**相同内容**并同步 → 不新增记录，提示「内容已存在，已刷新时间戳」
5. 点任意记录的 **「复制」** → 按钮变为「✓ 已复制」，去别处 Ctrl+V 验证

## 自动化验证

```powershell
pnpm run typecheck   # vue-tsc --noEmit
pnpm test            # 端到端：真实 Pinia store + 真实后端，12 个用例
pnpm run build       # vue-tsc --noEmit && vite build
```

`pnpm test` 用 Node 内置测试运行器 + 类型擦除直接跑 `tests/e2e.test.ts`，覆盖：
健康检查、首屏列表、上传新增、**自动标题格式**、**自定义标题**、相同内容去重、
**按标题/正文搜索**、排序、删除、清空、错误可读性。

- 破坏性用例（清空、`dev/reset`）**默认跳过**，需显式开启：`$env:E2E_ALLOW_DESTRUCTIVE='1'; pnpm test`
- 测试收尾会调用 `POST /api/v1/dev/reset` 恢复 4 条种子数据，跑完可直接接着手工验证
- **剪贴板读写依赖浏览器 API，不在自动化范围内**，需按上一节手工验证

## 目录结构

```
web/
├── index.html
├── vite.config.ts               # @vitejs/plugin-vue、@ 别名、端口 5273
├── tsconfig.json                # @/* 与 #src/* 两套别名（见下）
├── package.json                 # imports: #src/* → ./src/*
├── pnpm-workspace.yaml          # pnpm 11 项目设置（allowBuilds 放行 esbuild / vue-demi）
├── .npmrc                       # 只放 registry（pnpm 11 仅从此读取认证/registry）
├── scripts/
│   └── generate-api-types.mjs   # pnpm run gen:api 的入口
├── tests/
│   └── e2e.test.ts              # 端到端闭环测试（驱动 store + client，与框架无关）
├── src/
│   ├── main.ts                  # 挂载应用 + 安装 Pinia
│   ├── App.vue                  # 两栏布局 + 全局提示
│   ├── api/
│   │   └── client.ts            # ✅ axios 封装 + token 拦截器 + 错误归一化
│   ├── types/
│   │   └── api.d.ts             # ✅ 由 openapi-typescript 生成，勿手改
│   ├── utils/
│   │   ├── clipboard.ts         # ✅ 剪贴板读写（自身写入标志 + execCommand 降级）
│   │   └── format.ts            # ✅ 时间/大小/截断
│   ├── stores/                  # ✅ Pinia（setup store 写法）
│   │   ├── clipboardStore.ts    #   列表、分页、上传（含标题）、去重识别、删除、清空
│   │   └── userStore.ts         #   当前用户（第 4 步完善登录）
│   ├── composables/
│   │   ├── useClipboard.ts      # ✅ 读剪贴板 → 上传 的编排
│   │   ├── useCopy.ts           # ✅ 复制回剪贴板 + 「已复制」状态
│   │   ├── useAutoSave.ts       # ✅ 防抖自动保存
│   │   └── useWebSocket.ts      # ⬜ 第 5 步：实时同步（当前为占位实现）
│   └── components/
│       ├── ClipboardHistory.vue # 左栏：搜索/刷新/排序/清空 + 列表
│       ├── ClipboardItemCard.vue# 单条记录卡片（标题 + 正文 + 操作）
│       └── InputPanel.vue       # 右栏：标题 + 加高正文 + 自动保存
└── .env.example
```

> `views/` 目录暂未创建：当前只有一个页面，`App.vue` 直接承载。
> 第 4 步加入登录页时会按目标结构补 `views/`。

## 开发规范对照（AGENTS.md 第 8 节）

| 规范 | 落地位置 |
|------|----------|
| 组件用 `<script setup lang="ts">` | `src/**/*.vue` |
| 组件不直接调 axios | 全部经 `src/api/client.ts` |
| 组件不直接调 `navigator.clipboard` | 全部经 `src/utils/clipboard.ts` |
| 状态用 Pinia，避免 prop drilling | `src/stores/`（setup store） |
| 可复用逻辑放 composables | `src/composables/` |
| 类型从 `types/api.d.ts` 导入，不手写重复类型 | `client.ts` 统一 re-export |
| 剪贴板读取必须由用户手势触发 | `InputPanel.vue` 的同步按钮 |
| 写回剪贴板设标志位防死循环 | `utils/clipboard.ts` 的 `isSelfWrite()`（第 5 步监听使用） |
| 不用 `v-html` 渲染剪贴板内容 | 模板一律 `{{ }}`，让 Vue 自动转义 |

## 关于导入别名（两套并存，各有原因）

| 别名 | 解析方式 | 用在哪 |
|------|----------|--------|
| `@/*` | Vite `resolve.alias` + tsconfig `paths` | **所有 `.vue` 组件**、`main.ts` |
| `#src/*` | `package.json` 的 `imports` 字段 | **store / composables / api / utils** |

为什么不全用一套：

- Node 直接运行时**不读 tsconfig `paths`**，`@/xxx` 会被当成裸包名而报 `ERR_MODULE_NOT_FOUND`；
  而 `#src/*` 走 `package.json` 的 `imports`，Node 原生支持，端到端测试才能直接跑源码
- 因此**被端到端测试直接引入的模块必须用 `#src/*` 并带 `.ts` 扩展名**（Node ESM 要求显式扩展名）；
  纯 UI 层用更常见的 `@/*` 即可

改动这些模块时注意别把 `#src/` 换成 `@/`，否则 `pnpm test` 会报模块找不到。

## 契约变更后

```powershell
pnpm run gen:api     # 重新生成 src/types/api.d.ts
pnpm run typecheck   # 确认没有类型破坏
```
