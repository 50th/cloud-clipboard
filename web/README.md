# web —— 云剪贴板 Web 端

React 18 + TypeScript + Vite。当前处于 **第 2 步：Web 端骨架 + 单端闭环**。

## 快速开始

前置：后端已运行（见 `../server/README.md`）。

```powershell
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

> ⚠️ 必须用 `127.0.0.1` / `localhost` 访问。浏览器剪贴板 API **只在 HTTPS 或 localhost 下可用**，
> 用局域网 IP（如 `http://192.168.x.x:5273`）打开时读取会被浏览器拒绝。

## 界面结构

左右两栏：

- **左栏 · 历史记录**：搜索框（列表顶部）、刷新、排序、清空全部，以及记录列表。
  **所有历史相关操作都集中在左栏**，列表区域独立滚动。
- **右栏 · 剪贴板输入**：标题输入、加高正文编辑区（最小 240px）、
  上传 / 同步剪贴板 / 清空输入，以及自动保存开关与状态。

每条记录显示：**标题**、相对时间、正文（超长折叠并可展开）、复制 / 删除按钮。

## 标题规则

- 用户填写了标题 → 原样保存
- 留空或只填空格 → 服务端自动生成 `<用户名> · <月-日 时:分>`，例如 `demo · 10-03 12:55`
- 内容命中去重时，**不会**覆盖已有标题（除非本次显式传了标题）
- 搜索同时匹配**标题与正文**

## 自动保存

右栏默认开启，**停止输入 1.5 秒**后自动上传（`src/hooks/useAutoSave.ts`）。
界面上有开关可随时关闭，右下角显示状态（等待输入 / 待保存 / 保存中… / 已保存 hh:mm:ss）。

已知行为：每次改动产生一条记录（相同内容仍会被服务端去重）。若不想留下中间态记录，
关掉自动保存、改用「上传」按钮即可。`Ctrl+Enter` 可快速上传。

## 单端闭环手工验证

1. 在任意地方复制一段文字（Ctrl+C）
2. 点右栏 **「同步剪贴板」**（读取必须由点击手势触发，浏览器不允许后台自动读）
3. 左栏顶部出现新记录，提示「已同步剪贴板（新记录 …）」
4. 再复制一次**相同内容**并同步 → 不新增记录，提示「内容已存在，已刷新时间戳」
5. 点任意记录的 **「复制」** → 按钮变为「✓ 已复制」，去别处 Ctrl+V 验证

## 自动化验证

```powershell
pnpm run typecheck   # tsc --noEmit
pnpm test            # 端到端：真实 store + 真实后端，11 个用例
pnpm run build       # tsc --noEmit && vite build
```

`pnpm test` 用 Node 内置测试运行器 + 类型擦除直接跑 `tests/e2e.test.ts`，覆盖：
健康检查、首屏列表、上传新增、**自动标题格式**、**自定义标题**、相同内容去重、
**按标题/正文搜索**、排序、删除、清空、错误可读性。

测试收尾会调用后端 `POST /api/v1/dev/reset` 恢复 4 条种子数据，因此**跑完测试后可以直接接着手工验证**。
该接口仅在 `DEBUG=true` 时注册（见 `server/app/routers/dev.py`）。

**剪贴板读写依赖浏览器 API，不在自动化范围内，需按上一节手工验证。**

## 目录结构

```
web/
├── index.html
├── vite.config.ts               # 插件、@ 别名、固定端口 5273
├── tsconfig.json                # @/* 与 #src/* 两套别名
├── package.json                 # imports: #src/* → ./src/*
├── pnpm-workspace.yaml          # pnpm 11 项目设置（allowBuilds 放行 esbuild）
├── .npmrc                       # 只放 registry（pnpm 11 仅从此读取认证/registry）
├── scripts/
│   └── generate-api-types.mjs   # pnpm run gen:api 的入口
├── tests/
│   └── e2e.test.ts              # 端到端闭环测试（真实后端）
├── src/
│   ├── main.tsx                 # React 挂载点
│   ├── App.tsx                  # 两栏布局 + 全局提示
│   ├── api/
│   │   └── client.ts            # ✅ axios 封装 + token + 错误归一化 + devApi
│   ├── types/
│   │   └── api.d.ts             # ✅ 由 openapi-typescript 生成，勿手改
│   ├── utils/
│   │   ├── clipboard.ts         # ✅ 剪贴板读写（自身写入标志 + execCommand 降级）
│   │   └── format.ts            # ✅ 时间/大小/截断
│   ├── stores/
│   │   ├── clipboardStore.ts    # ✅ Zustand：列表、分页、上传（含标题）、去重识别、删除、清空
│   │   └── userStore.ts         # 当前用户（第 4 步完善登录）
│   ├── hooks/
│   │   ├── useClipboard.ts      # ✅ 读剪贴板 → 上传 的编排
│   │   ├── useCopy.ts           # ✅ 复制回剪贴板 + 「已复制」状态
│   │   ├── useAutoSave.ts       # ✅ 防抖自动保存
│   │   └── useWebSocket.ts      # ⬜ 第 5 步：实时同步（当前为占位实现）
│   └── components/
│       ├── ClipboardHistory.tsx # 左栏：搜索/刷新/排序/清空 + 列表
│       ├── ClipboardItemCard.tsx# 单条记录卡片（标题 + 正文 + 操作）
│       └── InputPanel.tsx       # 右栏：标题 + 加高正文 + 自动保存
└── .env.example
```

> `pages/` 目录暂未创建：当前只有一个页面，`App.tsx` 直接承载。
> 第 4 步加入登录页时会按目标结构补 `pages/`。

## 开发规范对照（AGENT.md 第 8 节）

| 规范 | 落地位置 |
|------|----------|
| 组件不直接调 axios | 全部经 `src/api/client.ts` |
| 组件不直接调 `navigator.clipboard` | 全部经 `src/utils/clipboard.ts` |
| 类型从 `types/api.d.ts` 导入，不手写重复类型 | `client.ts` 统一 re-export |
| 状态用 Zustand，避免 prop drilling | `src/stores/` |
| 剪贴板读取必须由用户手势触发 | `InputPanel.tsx` 的同步按钮 onClick |
| 写回剪贴板设标志位防死循环 | `utils/clipboard.ts` 的 `isSelfWrite()`（第 5 步监听使用） |

## 关于导入别名

项目同时支持两套别名，指向同一个 `src/`：

- `@/*` —— Vite 构建时别名（`vite.config.ts` + `tsconfig.json`）
- `#src/*` —— 通过 `package.json` 的 `imports` 字段，供 Node 直接运行时解析（端到端测试需要）

Node 的 `imports` 键不能以 `#/` 开头，且 ESM 要求显式文件扩展名，
因此源码中的 `#src/*` 导入必须写成 `#src/xxx.ts` 形式（`allowImportingTsExtensions` 已开启）。

## 契约变更后

```powershell
pnpm run gen:api     # 重新生成 src/types/api.d.ts
pnpm run typecheck   # 确认没有类型破坏
```
