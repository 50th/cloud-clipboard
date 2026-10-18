# harmony —— 云剪贴板鸿蒙端

**ArkTS + ArkUI（Stage 模型）**，API 12+。

## 构建

```powershell
# 仓库根目录
.\harmony\build.ps1              # 构建未签名 HAP
.\harmony\build.ps1 -Clean       # 先清理再构建
```

产物：`harmony/entry/build/default/outputs/default/entry-default-unsigned.hap`

> ⚠️ **务必用这个脚本，不要直接调 `hvigorw`。**
> hvigor 依赖三个环境变量，缺一个就以难以理解的错误失败：
>
> | 变量 | 缺失后果 |
> |------|---------|
> | `DEVECO_SDK_HOME` | 找不到 SDK |
> | `NODE_HOME` | hvigor 起不来 |
> | `JAVA_HOME` | 打包阶段报 **`spawn java ENOENT`**（错误码 00308018）——这个错看起来像签名问题，其实是缺 Java。需要指向 DevEco 自带的 JBR：`C:\Program Files\Huawei\DevEco Studio\jbr` |

## ⚠️ 安装与运行需要签名

**未签名的 HAP 不能安装到设备或模拟器**。构建脚本产出的是 `-unsigned.hap`，只能证明代码能编译。

要真正跑起来，二选一：

**方式一：用 DevEco Studio（推荐）**
1. 用 DevEco 打开 `harmony/` 目录
2. `File → Project Structure → Signing Configs`，勾选 **Automatically generate signature**
   （需登录华为开发者账号，DevEco 会自动申请调试证书与 Profile）
3. 直接点 Run，选择模拟器或真机

**方式二：命令行手动签名**
需要自行准备 `.p12` 密钥库、`.cer` 证书与 `.p7b` Profile，然后在
`harmony/build-profile.json5` 的 `app.signingConfigs` 中配置。
证书申请流程见华为官方文档「申请调试证书」。

> 本仓库的 `.gitignore` 已排除 `*.p12` / `*.p7b` / `*.cer` / `*.keystore`——
> **签名材料绝不入库**。

## ⚠️ 后端地址必须改（否则连不上）

设备上的 `127.0.0.1` 指向**设备自己**，不是你的电脑。因此：

1. **填电脑的局域网 IP**。两种方式，任选其一：
   - **应用内改（推荐，不用重新编译）**：打开 App 的登录页，在底部「后端地址」输入框填写并点「保存」
   - **改默认值**：编辑 `entry/src/main/ets/common/Config.ets` 的 `DEFAULT_API_BASE_URL`
     （当前填的是 `192.168.3.54:8000`），登录页的输入框会以它为初值
2. **让后端监听所有网卡**（只监听 `127.0.0.1` 时任何设备都连不上）：
   ```powershell
   .\scripts\start_server_lan.ps1          # 自动打印可用 IP 并以 --host 0.0.0.0 启动
   ```
   等价于：`cd server && .\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. 确认手机与电脑在同一局域网，且**防火墙放行 8000 端口**

查电脑局域网 IP：`Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^127\.' }`

## 权限说明

| 权限 | 授权方式 | 用途 |
|------|---------|------|
| `ohos.permission.INTERNET` | system_grant（自动） | 访问后端 API 与 WebSocket |
| `ohos.permission.READ_PASTEBOARD` | **user_grant（需用户同意）** | 读取系统剪贴板以自动同步 |

- **写入**剪贴板与**监听变化**（`on('update')`）都不需要权限
- 读取权限被拒时，应用仍可正常使用：点记录上的「复制」写回剪贴板不受影响，
  只是无法自动把系统剪贴板同步到云端（界面会给出提示）

> ⚠️ `READ_PASTEBOARD` 在 SDK 里的 `availableLevel` 是 `system_basic`。
> 普通应用（APL `normal`）能否通过运行时弹窗拿到该权限，**尚未实测验证**——
> 需要签名后在真机/模拟器上确认。若拿不到，自动同步不可用，属已知限制。

## 目录结构

```
harmony/
├── build.ps1                    # 构建脚本（封装三个环境变量）
├── build-profile.json5          # 应用级构建配置（签名配置填在这里）
├── oh-package.json5             # 依赖声明
├── AppScope/
│   └── app.json5                # bundleName / 版本 / 应用图标
└── entry/                       # 主模块
    ├── build-profile.json5
    └── src/main/
        ├── module.json5         # 权限、Ability、页面路由
        ├── ets/
        │   ├── entryability/EntryAbility.ets   # 入口，首屏加载登录页
        │   ├── common/
        │   │   ├── Config.ets                  # ⚠️ 后端地址在这里
        │   │   ├── Routes.ets                  # 页面路由常量 + 编辑页参数契约
        │   │   └── AppStore.ets                # 状态与业务编排（单例）
        │   ├── models/Types.ets                # 与后端 Schema 严格对齐
        │   ├── services/
        │   │   ├── ApiClient.ets               # REST：认证 + 剪贴板 CRUD
        │   │   ├── ClipboardService.ets        # 剪贴板读写 + 监听 + 自身写入防护
        │   │   └── WebSocketService.ets        # 实时同步：心跳 + 退避重连
        │   └── pages/
        │       ├── LoginPage.ets               # 登录 / 注册
        │       ├── ClipboardPage.ets           # 列表页：浏览 / 搜索 / 复制 / 删除
        │       └── EditPage.ets                # 编辑页：输入 + 自动保存倒计时
        └── resources/base/profile/main_pages.json
```

## 实现要点

**手动上传是兜底入口**：读取系统剪贴板依赖 `READ_PASTEBOARD`，而该权限能否授予尚未验证。
因此列表页提供「＋ 新建」入口——即使拿不到权限，用户仍能把文字送到云端。
（搜索、排序、长内容展开、删除/清空二次确认也已与 Web 端对齐。）

**列表页与编辑页是分开的两个页面**：列表页只管浏览（搜索/排序/刷新/复制/删除/清空/分页），
点条目的标题或内容、或点「＋ 新建」，跳转到编辑页（`pages/EditPage`）。
拆开是因为编辑页有自己的输入状态与倒计时，混在列表页里时列表刷新、剪贴板监听、
搜索都会干扰同一份状态。

**从编辑页返回时列表会刷新**：列表页在 `onPageShow` 里**重新订阅** store 并主动拉一次。
⚠️ 只靠 `aboutToAppear` 订阅是不够的——页面被 `pushUrl` 覆盖时若触发了
`aboutToDisappear`，监听会被退订，而返回时 `aboutToAppear` 不会再执行，
列表就永远停在旧数据上。每页另有「刷新」按钮可手动拉取。

**编辑页的自动保存**：默认开启，**停止输入 2 秒**后保存，界面上有真实递减的倒计时。
保存复用同一条记录——反复保存只更新那一行，不会每个中间态都新建一行。
- 点条目进入 → 载入**最新**内容（按 id 重新拉一次，而不是用列表里的旧快照）
- 新建页首次保存成功后，页头从「新建记录」变为「编辑记录 · <标题>」
- 点「← 返回」会先保存再离开；系统返回手势也做了兜底落盘

⚠️ **自动保存由输入回调显式触发，不用 `@Watch` 装饰器。**
`@Watch` 一旦没如期触发，倒计时完全不会启动且不报任何错，表现为"自动保存没生效"，
极难排查（上一版就是这么静默失效的）。

**循环同步防护**：写回剪贴板会触发 `on('update')`，不加处理会形成
"写入 → 触发 → 再上传"的死循环。`ClipboardService.isSelfWrite()` 用 800ms 窗口
忽略自身写入触发的更新，与 Web 端 `web/src/utils/clipboard.ts` 策略一致。

**去重交给服务端**：同一内容重复上传由后端 `UNIQUE(user_id, content_hash)` 处理，
客户端不做去重判断，避免两端规则不一致。

**收到事件只刷新列表**：WebSocket 事件不用于本地合并，而是静默重新拉取当前页——
排序、分页都会影响"该出现哪些记录"，本地合并容易与后端规则不一致。

**令牌无效不重连**：服务端以关闭码 `4401` 表示令牌失效，此时重连没有意义，
客户端会停止重连并回到登录页。

## 已验证与未验证

| 项 | 状态 |
|----|------|
| ArkTS 编译 | ✅ 已通过（`hvigor BUILD SUCCESSFUL`） |
| HAP 打包 | ✅ 产出 324 KB 未签名 HAP |
| 安装到设备/模拟器 | ⬜ **未验证**（缺签名材料） |
| 与后端联调 | ⬜ **未验证**（需先解决签名与网络） |
| `READ_PASTEBOARD` 能否授予 | ⬜ **未验证** |

> 手动上传 / 载入编辑 / 自动保存倒计时 / 搜索 / 排序 / 二次确认等界面
> **仅经编译验证**，未在设备上实际点击验证。

## 真机联调步骤

前置：已用 DevEco 配好签名（见上）；后端已用 `.\scripts\start_server_lan.ps1` 以 `0.0.0.0` 启动。

1. 电脑上运行 `.\scripts\start_server_lan.ps1`，记下它打印的局域网 IP
2. 在 DevEco 里 Run 到真机 / 模拟器
3. 登录页底部「后端地址」填 `http://<上一步的IP>:8000` → 点「保存」
4. 注册或登录（演示账号 `demo` / `demo1234`，见 [`../server/README.md`](../server/README.md)）
5. 点「＋ 新建」→ 进入编辑页，输入内容 → 停止输入 2 秒后应自动保存（状态会从
   「2 秒后自动保存」递减到保存完成）；返回列表应看到该条
6. **点列表条目的标题/内容** → 进入编辑页并载入该条，改完保存后列表**不新增**一行
7. 同账号在 Web 端确认能否收到实时推送，反向亦然（验证 WebSocket）
8. 点「同步剪贴板」，据此判定 `READ_PASTEBOARD` 是否可用：
   - 读得到 → 自动同步可用
   - 读不到（提示无权限）→ 属**已知限制**，手动上传仍可用
8. 点记录上的「复制」，到其它 App 粘贴，确认写回剪贴板成功
