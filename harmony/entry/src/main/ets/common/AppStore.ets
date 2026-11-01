/**
 * 应用状态与业务编排（单例）。
 *
 * 页面只负责渲染与调用这里的方法，业务逻辑集中在本文件——
 * 与 Web 端的 `stores/` 职责一致。
 */
import { common } from '@kit.AbilityKit';

import { ApiClient, ApiError } from '../services/ApiClient';
import { ClipboardService } from '../services/ClipboardService';
import { WebSocketService } from '../services/WebSocketService';
import { loadApiBaseUrl, loadToken, saveApiBaseUrl, saveToken } from '../common/Config';
import {
  AuthResponse,
  ClipboardItem,
  ClipboardItemCreate,
  ClipboardItemUpdate,
  SortOrder,
  UserInfo,
  WsEnvelope,
} from '../models/Types';

/** 每页条数，与后端默认值一致。 */
export const PAGE_SIZE: number = 20;

/**
 * 本机时区（IANA 名，如 `Asia/Shanghai`）。
 *
 * 传给后端用于生成自动标题里的时间文本——数据库统一存 UTC，
 * 时区只影响标题怎么显示。
 */
function localTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch (error) {
    return 'Asia/Shanghai';
  }
}

export class AppStore {
  private static instance: AppStore | null = null;

  readonly api: ApiClient;
  readonly clipboard: ClipboardService;
  private context: common.UIAbilityContext;

  // ---- 可观察状态（页面读取后自行刷新）----
  items: ClipboardItem[] = [];
  total: number = 0;
  page: number = 1;
  pages: number = 0;
  /** 搜索关键字（同时匹配标题与内容），空串表示不过滤 */
  search: string = '';
  /** 排序方向 */
  order: SortOrder = SortOrder.DESC;
  user: UserInfo | null = null;
  loading: boolean = false;
  errorMessage: string = '';
  /** WebSocket 是否在线 */
  realtimeConnected: boolean = false;
  /**
   * 正在编辑的记录被**其他设备**更新时的最新版本（null 表示没有待确认的更新）。
   *
   * 保存是后写覆盖、没有版本号校验，所以至少要让用户知道"别处已经改过这一条"。
   */
  remoteUpdate: ClipboardItem | null = null;

  private socket: WebSocketService | null = null;
  private pageListeners: (() => void)[] = [];

  /**
   * 保存时**更新**哪一条记录（null 表示新建）。
   *
   * 它包含「自动保存刚建出来的记录」——后续保存复用同一条，
   * 否则打一段字就会在列表里冒出好几行。
   * 「当前是不是在编辑某个已有记录」由编辑页自己的状态表示，不放在这里：
   * 那是界面关注点，混进 store 只会让两边各存一份、迟早不一致。
   */
  private saveTargetId: string | null = null;
  /** 已保存内容的签名，用于判断"有没有未保存的改动" */
  private savedContent: string = '';
  private savedTitle: string = '';
  /**
   * 正在提交中的内容。
   *
   * 服务端保存成功后也会广播 `clipboard.updated`，回显可能比 HTTP 响应先到；
   * 不记录在途内容的话，会把自己的保存误判成"其他设备改了这一条"。
   */
  private inFlightContent: string = '';

  private constructor(context: common.UIAbilityContext) {
    this.context = context;
    this.api = new ApiClient(context);
    this.clipboard = new ClipboardService(context);
  }

  /** 取全局唯一实例。 */
  static get(context: common.UIAbilityContext): AppStore {
    if (AppStore.instance === null) {
      AppStore.instance = new AppStore(context);
    }
    return AppStore.instance;
  }

  /** 页面注册刷新回调，状态变化时被调用。 */
  subscribe(listener: () => void): void {
    this.pageListeners.push(listener);
  }

  /** 页面销毁时取消注册。 */
  unsubscribe(listener: () => void): void {
    this.pageListeners = this.pageListeners.filter((item: () => void) => item !== listener);
  }

  private notify(): void {
    this.pageListeners.forEach((listener: () => void) => listener());
  }

  // ---- 配置与认证 ----

  get baseUrl(): string {
    return this.api.currentBaseUrl;
  }

  /** 修改后端地址并立即生效（真机调试时常用）。 */
  setBaseUrl(url: string): void {
    saveApiBaseUrl(this.context, url);
    this.api.refresh();
  }

  get isLoggedIn(): boolean {
    return this.api.hasToken;
  }

  /** 登录并建立实时连接。 */
  async login(username: string, password: string): Promise<boolean> {
    try {
      const result: AuthResponse = await this.api.login(username, password);
      saveToken(this.context, result.token.access_token);
      this.api.refresh();
      this.user = {
        id: result.id,
        username: result.username,
        email: result.email,
        nickname: result.nickname,
        avatar_url: result.avatar_url,
        created_at: result.created_at,
      };
      this.errorMessage = '';
      this.startRealtime();
      await this.refreshItems();
      return true;
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
      return false;
    }
  }

  /** 注册（成功即已登录）。 */
  async register(username: string, email: string, password: string): Promise<boolean> {
    try {
      const result: AuthResponse = await this.api.register(username, email, password);
      saveToken(this.context, result.token.access_token);
      this.api.refresh();
      this.user = {
        id: result.id,
        username: result.username,
        email: result.email,
        nickname: result.nickname,
        avatar_url: result.avatar_url,
        created_at: result.created_at,
      };
      this.errorMessage = '';
      this.startRealtime();
      await this.refreshItems();
      return true;
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
      return false;
    }
  }

  /** 用本地令牌恢复会话（启动时调用）。 */
  async restoreSession(): Promise<void> {
    if (!this.api.hasToken) {
      return;
    }
    try {
      this.user = await this.api.me();
      this.startRealtime();
      await this.refreshItems();
    } catch (error) {
      // 令牌过期或被吊销：清掉本地状态回到登录页
      this.logout();
    }
  }

  /** 退出登录：断开实时连接、清除令牌与列表。 */
  logout(): void {
    this.stopRealtime();
    saveToken(this.context, '');
    this.api.refresh();
    this.user = null;
    this.items = [];
    this.total = 0;
    this.pages = 0;
    this.page = 1;
    this.search = '';
    this.order = SortOrder.DESC;
    this.errorMessage = '';
    this.saveTargetId = null;
    this.savedContent = '';
    this.savedTitle = '';
    this.remoteUpdate = null;
    this.notify();
  }

  // ---- 列表 ----

  /** 拉取当前页。 */
  async refreshItems(silent: boolean = false): Promise<void> {
    if (!silent) {
      this.loading = true;
      this.notify();
    }
    try {
      const result = await this.api.listItems(this.page, PAGE_SIZE, this.order, this.search);
      this.items = result.items;
      this.total = result.total;
      this.pages = result.pages;
      this.errorMessage = '';
    } catch (error) {
      this.errorMessage = this.describe(error);
    } finally {
      this.loading = false;
      this.notify();
    }
  }

  async setPage(page: number): Promise<void> {
    this.page = page;
    await this.refreshItems();
  }

  /** 设置搜索关键字（重置到第 1 页）。 */
  async setSearch(keyword: string): Promise<void> {
    this.search = keyword.trim();
    this.page = 1;
    await this.refreshItems();
  }

  /** 切换排序方向（重置到第 1 页）。 */
  async setOrder(order: SortOrder): Promise<void> {
    this.order = order;
    this.page = 1;
    await this.refreshItems();
  }

  // ---- 写操作 ----

  /**
   * 上传一段文字（**总是新建**）。
   *
   * 用于「同步剪贴板」与剪贴板监听：那些是独立的一条新记录，
   * 不应该覆盖用户正在编辑的内容。要保存编辑用 `saveEdits`。
   *
   * 服务端**内置去重**：相同内容不会新建记录，只刷新时间戳。
   */
  async upload(text: string, title?: string): Promise<ClipboardItem | null> {
    const content = text.trim();
    if (content.length === 0) {
      this.errorMessage = '内容为空，未上传';
      this.notify();
      return null;
    }
    try {
      const payload: ClipboardItemCreate = {
        content: content,
        timezone: localTimezone(),
      };
      if (title !== undefined && title.trim().length > 0) {
        payload.title = title.trim();
      }
      const item = await this.api.createItem(payload);
      this.errorMessage = '';
      await this.refreshItems(true);
      return item;
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
      return null;
    }
  }

  // ---- 编辑与自动保存 ----

  /**
   * 把一条已有记录载入编辑。
   *
   * 之后调用 `saveEdits` 会**更新这一条**，而不是新建——
   * 否则「点开一条 → 改几个字 → 保存」会多出一行。
   */
  loadForEdit(item: ClipboardItem): void {
    this.saveTargetId = item.id;
    // 与 hasUnsavedChanges 的归一化保持一致（都按 trim 后比较）
    this.savedContent = item.content.trim();
    this.savedTitle = item.title.trim();
    this.remoteUpdate = null;
    this.errorMessage = '';
    this.notify();
  }

  /**
   * 解除编辑/草稿关联：之后保存会新建一条。
   *
   * 用户点「新建」或想放弃当前编辑对象时调用。
   */
  startNew(): void {
    this.saveTargetId = null;
    this.savedContent = '';
    this.savedTitle = '';
    this.remoteUpdate = null;
    this.notify();
  }

  /**
   * 当前输入相对上次保存是否有改动（空内容也算无改动）。
   *
   * ⚠️ 必须用**与保存时相同的归一化方式**（trim）比较：保存送出的是 trim 后的值，
   * 若这里比较原始值，用户输入带尾随空格时会被永远判成"未保存"，
   * 导致每 2 秒保存一次、无限循环。
   */
  hasUnsavedChanges(content: string, title: string): boolean {
    const trimmedContent = content.trim();
    if (trimmedContent.length === 0) {
      return false;
    }
    return trimmedContent !== this.savedContent || title.trim() !== this.savedTitle;
  }

  /**
   * 保存当前输入（自动保存与手动保存共用）。
   *
   * - 已有保存目标 → `PATCH` 更新那一条
   * - 没有 → 新建一条，并把后续保存指向它（避免打字过程中冒出多行）
   *
   * 记录若已被别处删除（404），自动回退为新建，用户无感知。
   */
  async saveEdits(content: string, title: string): Promise<ClipboardItem | null> {
    const trimmedContent = content.trim();
    if (trimmedContent.length === 0) {
      this.errorMessage = '内容为空，未保存';
      this.notify();
      return null;
    }
    const trimmedTitle = title.trim();

    if (this.saveTargetId !== null) {
      const targetId = this.saveTargetId;
      this.inFlightContent = trimmedContent;
      try {
        const payload: ClipboardItemUpdate = {
          content: trimmedContent,
          timezone: localTimezone(),
        };
        if (trimmedTitle.length > 0) {
          payload.title = trimmedTitle;
        }
        const item = await this.api.updateItem(targetId, payload);
        this.markSaved(trimmedContent, trimmedTitle);
        // 已经用本地版本覆盖，提示不再需要
        this.remoteUpdate = null;
        this.errorMessage = '';
        await this.refreshItems(true);
        return item;
      } catch (error) {
        // 记录已被删除（本机或别的设备）→ 丢掉关联，走下面的新建分支
        if (!(error instanceof ApiError) || error.status !== 404) {
          this.errorMessage = this.describe(error);
          this.notify();
          return null;
        }
        this.saveTargetId = null;
      } finally {
        this.inFlightContent = '';
      }
    }

    try {
      const payload: ClipboardItemCreate = {
        content: trimmedContent,
        timezone: localTimezone(),
      };
      if (trimmedTitle.length > 0) {
        payload.title = trimmedTitle;
      }
      const item = await this.api.createItem(payload);
      // 后续保存复用这一条，避免打字过程中冒出多行
      this.saveTargetId = item.id;
      this.markSaved(trimmedContent, trimmedTitle);
      this.errorMessage = '';
      await this.refreshItems(true);
      return item;
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
      return null;
    }
  }

  private markSaved(content: string, title: string): void {
    this.savedContent = content;
    this.savedTitle = title;
  }

  /**
   * 载入其他设备的最新版本（会丢弃本地未保存的改动），并返回它。
   *
   * 编辑页拿到返回值后更新输入框；之后保存仍更新同一条记录。
   */
  applyRemoteUpdate(): ClipboardItem | null {
    const item = this.remoteUpdate;
    if (item === null) {
      return null;
    }
    this.remoteUpdate = null;
    this.saveTargetId = item.id;
    this.savedContent = item.content.trim();
    this.savedTitle = item.title.trim();
    return item;
  }

  /** 忽略远端更新提示，继续用本地版本编辑/保存。 */
  dismissRemoteUpdate(): void {
    this.remoteUpdate = null;
  }

  /** 删除一条记录。 */
  async remove(itemId: string): Promise<void> {
    try {
      await this.api.deleteItem(itemId);
      // 删掉的正是保存目标 → 丢掉关联，下次保存会新建
      if (this.saveTargetId === itemId) {
        this.saveTargetId = null;
      }
      if (this.remoteUpdate !== null && this.remoteUpdate.id === itemId) {
        this.remoteUpdate = null;
      }
      await this.refreshItems(true);
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
    }
  }

  /** 清空全部记录。 */
  async clearAll(): Promise<void> {
    try {
      await this.api.clearItems();
      this.page = 1;
      this.saveTargetId = null;
      this.savedContent = '';
      this.savedTitle = '';
      this.remoteUpdate = null;
      await this.refreshItems(true);
    } catch (error) {
      this.errorMessage = this.describe(error);
      this.notify();
    }
  }

  /** 写入系统剪贴板（内部会打自身写入标记，避免循环）。 */
  async copyToClipboard(text: string): Promise<boolean> {
    return await this.clipboard.writeText(text);
  }

  // ---- 剪贴板监听 ----

  /**
   * 开始监听剪贴板变化并自动上传。
   *
   * 先申请读取权限；**监听本身不需要权限**，所以即使拒绝也会继续监听
   * （只是回调里读不到内容）。返回值表示是否拿到了读取权限。
   */
  async startClipboardMonitor(): Promise<boolean> {
    const granted = await this.clipboard.requestReadPermission();
    this.clipboard.startWatching((text: string) => {
      // 剪贴板变化 → 自动上传；去重由服务端负责
      this.upload(text).catch(() => {
        // 上传失败已在 upload 内部记录到 errorMessage
      });
    });
    this.notify();
    return granted;
  }

  /** 停止剪贴板监听（页面销毁时调用）。 */
  stopClipboardMonitor(): void {
    this.clipboard.stopWatching();
  }

  get isMonitoring(): boolean {
    return this.clipboard.hasReadPermission();
  }

  // ---- 实时同步 ----

  private startRealtime(): void {
    this.stopRealtime();
    const socket = new WebSocketService(this.api.currentBaseUrl, loadToken(this.context));
    this.socket = socket;
    socket.connect(
      (connected: boolean) => {
        this.realtimeConnected = connected;
        this.notify();
      },
      (envelope: WsEnvelope) => {
        this.handleRealtimeEvent(envelope);
        // 收到任何剪贴板事件都静默刷新当前页：
        // 排序、分页都会影响"该出现哪些记录"，本地合并容易与后端规则不一致
        this.refreshItems(true).catch(() => {});
      },
      () => {
        // 重连成功：断线期间可能漏事件
        this.refreshItems(true).catch(() => {});
      },
    );
  }

  private stopRealtime(): void {
    if (this.socket !== null) {
      this.socket.disconnect();
      this.socket = null;
    }
    this.realtimeConnected = false;
  }

  /**
   * 处理实时事件：只关心「正在编辑的那条记录被**其他设备**更新」。
   *
   * 自己保存也会收到同一条广播，因此内容与已保存内容/在途内容一致时不算远端修改。
   * 命中时只记录并通知页面，不直接改页面上的输入内容——先由用户决定怎么处理。
   */
  private handleRealtimeEvent(envelope: WsEnvelope): void {
    if (envelope.event !== 'clipboard.updated' || this.saveTargetId === null) {
      return;
    }
    const item = envelope.data as ClipboardItem;
    if (item === undefined || item === null || item.id !== this.saveTargetId) {
      return;
    }
    const content = item.content.trim();
    if (content === this.savedContent || content === this.inFlightContent) {
      return;
    }
    this.remoteUpdate = item;
    this.notify();
  }

  /** 把异常转成可读提示。 */
  private describe(error: Object): string {
    if (error instanceof ApiError) {
      return error.message;
    }
    const err = error as Error;
    return err.message ?? '未知错误';
  }
}

/** 重新导出，页面 import 更集中。 */
export { loadApiBaseUrl };
