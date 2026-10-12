/**
 * 剪贴板读写与变化监听。
 *
 * ## 权限（关键）
 * - **读取**需要 `ohos.permission.READ_PASTEBOARD`，且它是 **user_grant**：
 *   必须运行时向用户申请，不能靠清单声明自动获得。
 * - **监听** `on('update')` **不需要任何权限**。
 * - **写入**不需要权限。
 *
 * ⚠️ 因此"同步到云端"的能力依赖用户授权。若授权被拒，本应用户仍可手动粘贴，
 *    只是无法自动读取系统剪贴板（界面会给出提示，见 `Pages`）。
 *
 * ## 循环同步防护
 * 写回剪贴板会触发 `on('update')`，若不加处理会形成"写入 → 触发 → 再上传"的死循环。
 * 用 `isSelfWrite()` 标志位解决：写入后一段时间内的更新事件被忽略。
 * Web 端（`web/src/utils/clipboard.ts`）用同样的策略。
 */
import { abilityAccessCtrl, common, Permissions } from '@kit.AbilityKit';
import { pasteboard } from '@kit.BasicServicesKit';

/** 自身写入后的忽略窗口（毫秒）。 */
export const SELF_WRITE_WINDOW_MS: number = 800;

const READ_PERMISSION: Permissions = 'ohos.permission.READ_PASTEBOARD';

/** 剪贴板监听者：收到"剪贴板变了"的通知。 */
export type ClipboardChangeListener = (text: string) => void;

export class ClipboardService {
  private context: common.UIAbilityContext;
  /** 上次由本应用写入的时间戳；0 表示没有正在进行的自身写入。 */
  private lastSelfWriteAt: number = 0;
  private listener: ClipboardChangeListener | null = null;
  /** 绑定到 pasteboard 的回调必须保存引用，否则 off() 无法精确解绑。 */
  private pasteboardCallback: (() => void) | null = null;
  private watching: boolean = false;

  constructor(context: common.UIAbilityContext) {
    this.context = context;
  }

  /**
   * 是否处于"自身写入"窗口内。
   *
   * 监听逻辑据此忽略自己触发的变化，避免死循环。
   */
  isSelfWrite(): boolean {
    if (this.lastSelfWriteAt === 0) {
      return false;
    }
    const elapsed = Date.now() - this.lastSelfWriteAt;
    if (elapsed > SELF_WRITE_WINDOW_MS) {
      this.lastSelfWriteAt = 0;
      return false;
    }
    return true;
  }

  /**
   * 向用户申请读取剪贴板的权限，返回是否已授权。
   *
   * 重复调用是安全的：已授权时会立即返回 true。
   */
  async requestReadPermission(): Promise<boolean> {
    const manager = abilityAccessCtrl.createAtManager();
    try {
      // 用 Sync 版本：`checkAccessToken` 返回 Promise，而这里需要一个同步判定
      if (manager.checkAccessTokenSync(
        this.context.applicationInfo.accessTokenId,
        READ_PERMISSION,
      ) === abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED) {
        return true;
      }
    } catch (error) {
      // 查询失败时继续走申请流程，让用户看到明确结果
    }

    try {
      const result = await manager.requestPermissionsFromUser(this.context, [READ_PERMISSION]);
      const codes: number[] = result.authResults;
      return codes.length > 0 && codes[0] === abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED;
    } catch (error) {
      return false;
    }
  }

  /** 当前是否已获得读取权限（不弹窗）。 */
  hasReadPermission(): boolean {
    try {
      const manager = abilityAccessCtrl.createAtManager();
      return (
        manager.checkAccessTokenSync(
          this.context.applicationInfo.accessTokenId,
          READ_PERMISSION,
        ) === abilityAccessCtrl.GrantStatus.PERMISSION_GRANTED
      );
    } catch (error) {
      return false;
    }
  }

  /**
   * 读取系统剪贴板的纯文本。
   *
   * 返回空字符串表示剪贴板为空、内容不是文本，或**没有读取权限**。
   * 调用方可通过 `hasReadPermission()` 区分后两种情况。
   */
  async readText(): Promise<string> {
    try {
      const board = pasteboard.getSystemPasteboard();
      const has = await board.hasData();
      if (!has) {
        return '';
      }
      const data = await board.getData();
      return data.getPrimaryText();
    } catch (error) {
      // 无权限或系统拒绝时走这里，返回空串让调用方给出提示
      return '';
    }
  }

  /**
   * 写入纯文本到系统剪贴板。
   *
   * 会先打上"自身写入"标记，避免触发自己注册的监听造成循环。
   */
  async writeText(text: string): Promise<boolean> {
    try {
      const data = pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, text);
      // 只在应用内可粘贴，减少内容外泄到其他应用的机会
      const property = data.getProperty();
      property.localOnly = true;
      property.tag = 'cloud-clipboard';
      data.setProperty(property);

      this.lastSelfWriteAt = Date.now();
      await pasteboard.getSystemPasteboard().setData(data);
      return true;
    } catch (error) {
      this.lastSelfWriteAt = 0;
      return false;
    }
  }

  /**
   * 开始监听剪贴板变化。
   *
   * **监听本身不需要权限**，但读取内容需要，所以回调里拿到的是空串时
   * 通常意味着没授权。回调会被"自身写入窗口"过滤。
   */
  startWatching(listener: ClipboardChangeListener): void {
    if (this.watching) {
      return;
    }
    this.listener = listener;

    const callback = (): void => {
      if (this.isSelfWrite()) {
        // 自己刚写进去的，忽略，否则会"写入→触发→上传"无限循环
        return;
      }
      if (this.listener !== null) {
        this.readText().then((text: string) => {
          if (text.length > 0 && this.listener !== null) {
            this.listener(text);
          }
        });
      }
    };

    this.pasteboardCallback = callback;
    pasteboard.getSystemPasteboard().on('update', callback);
    this.watching = true;
  }

  /** 停止监听。务必在页面销毁时调用，否则会持有回调造成泄漏。 */
  stopWatching(): void {
    if (!this.watching) {
      return;
    }
    try {
      if (this.pasteboardCallback !== null) {
        pasteboard.getSystemPasteboard().off('update', this.pasteboardCallback);
      }
    } catch (error) {
      // 已经解绑或系统异常，忽略
    }
    this.pasteboardCallback = null;
    this.listener = null;
    this.watching = false;
  }
}
