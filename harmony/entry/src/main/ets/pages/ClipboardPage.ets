/**
 * 剪贴板列表页（主页面）。
 *
 * 承担：手动输入上传、列表展示、搜索与排序、手动同步系统剪贴板、
 * 点击复制回剪贴板、删除、清空，并显示 WebSocket 实时连接状态。
 *
 * ⚠️ **手动上传是必备能力**：读取系统剪贴板需要 `READ_PASTEBOARD` 权限，
 * 而该权限能否授予尚未验证（见 harmony/README.md）。没有它时，页面上的
 * 输入框是唯一能把文字送到云端的入口，因此不能只依赖「同步剪贴板」。
 */
import { common } from '@kit.AbilityKit';
import { router } from '@kit.ArkUI';

import { AppStore } from '../common/AppStore';
import { ClipboardItem, SortOrder } from '../models/Types';

/** 超过该长度的内容在卡片里折叠显示。与 Web 端 `ClipboardItemCard.vue` 一致。 */
const COLLAPSE_LENGTH: number = 160;

/** 自动保存：停止输入多久后保存（毫秒）。与 Web 端保持一致的 2 秒。 */
const AUTO_SAVE_DELAY_MS: number = 2000;
/** 倒计时刷新间隔（毫秒）。200ms 足够让秒数看起来连续，又不至于太耗电。 */
const AUTO_SAVE_TICK_MS: number = 200;

@Entry
@Component
struct ClipboardPage {
  @State items: ClipboardItem[] = [];
  @State total: number = 0;
  @State page: number = 1;
  @State pages: number = 0;
  @State loading: boolean = false;
  @State message: string = '';
  @State isError: boolean = false;
  @State realtimeConnected: boolean = false;
  @State monitoring: boolean = false;
  @State username: string = '';

  // ---- 搜索与排序 ----
  @State searchInput: string = '';
  /** 已生效的搜索词（store 里的值），空串表示未筛选 */
  @State search: string = '';
  @State order: SortOrder = SortOrder.DESC;

  // ---- 手动输入上传 ----
  @State showInput: boolean = false;
  @State @Watch('onDraftChanged') draftTitle: string = '';
  @State @Watch('onDraftChanged') draftContent: string = '';

  // ---- 自动保存 ----
  /** 自动保存开关 */
  @State autoSave: boolean = true;
  /** 倒计时剩余毫秒（0 表示未在计时） */
  @State remainingMs: number = 0;
  /** 是否有未保存改动（倒计时进行中） */
  @State pending: boolean = false;
  /** 是否正在保存 */
  @State saving: boolean = false;

  // ---- 正在编辑的已有记录 ----
  /** 正在编辑的记录 id；空串表示不是显式编辑 */
  @State editingId: string = '';
  /** 正在编辑的记录标题（仅用于提示"在改哪一条"） */
  @State editingTitle: string = '';

  /** 已展开的长内容 id 列表（ArkUI 无法逐项维护状态，统一在此记录） */
  @State expandedIds: string[] = [];

  private store: AppStore | null = null;
  /** 保存监听回调引用，页面销毁时才能正确取消注册 */
  private listener: (() => void) | null = null;
  /** 自动保存倒计时计时器句柄 */
  private countdownTimer: number = -1;

  aboutToAppear(): void {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = AppStore.get(context);

    // 未登录时踢回登录页（例如令牌过期）
    if (!this.store.isLoggedIn) {
      router.replaceUrl({ url: 'pages/LoginPage' }).catch(() => {});
      return;
    }

    const store = this.store;
    this.search = store.search;
    this.order = store.order;
    this.listener = () => {
      this.syncFromStore();
    };
    store.subscribe(this.listener);

    store.restoreSession().then(() => {
      this.startMonitor();
    });
  }

  aboutToDisappear(): void {
    // 必须清理：否则监听、WebSocket 与倒计时会在页面销毁后继续跑
    this.stopCountdown();
    if (this.store !== null) {
      if (this.listener !== null) {
        this.store.unsubscribe(this.listener);
        this.listener = null;
      }
      this.store.stopClipboardMonitor();
    }
  }

  /** 把 store 的状态同步到页面 @State（ArkUI 不会自动跟踪普通对象属性）。 */
  private syncFromStore(): void {
    if (this.store === null) {
      return;
    }
    this.items = this.store.items;
    this.total = this.store.total;
    this.page = this.store.page;
    this.pages = this.store.pages;
    this.search = this.store.search;
    this.order = this.store.order;
    this.loading = this.store.loading;
    this.realtimeConnected = this.store.realtimeConnected;
    this.monitoring = this.store.isMonitoring;
    this.username = this.store.user?.username ?? '';
    this.editingId = this.store.editingId ?? '';
    const error = this.store.errorMessage;
    if (error.length > 0) {
      this.message = error;
      this.isError = true;
    }
  }

  private setMessage(text: string, isError: boolean = false): void {
    this.message = text;
    this.isError = isError;
  }

  private async startMonitor(): Promise<void> {
    if (this.store === null) {
      return;
    }
    const granted = await this.store.startClipboardMonitor();
    if (!granted) {
      this.setMessage(
        '未获得剪贴板读取权限：可在上方「新建/粘贴上传」里手动输入内容，复制功能不受影响',
        true,
      );
    } else {
      this.setMessage('已开启剪贴板监听：复制内容会自动同步');
    }
    this.syncFromStore();
  }

  // ---- 自动保存倒计时 ----

  /** 输入变化时重启倒计时（`@Watch` 回调）。 */
  private onDraftChanged(): void {
    this.restartCountdown();
  }

  /** 停止倒计时并复位状态。 */
  private stopCountdown(): void {
    if (this.countdownTimer !== -1) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = -1;
    }
    this.pending = false;
    this.remainingMs = 0;
  }

  /**
   * 重启倒计时。
   *
   * 只有**确实有未保存改动**时才计时：载入一条记录、或刚保存完，
   * 内容与已保存的一致，不该再触发一次保存。
   */
  private restartCountdown(): void {
    this.stopCountdown();
    if (!this.autoSave || this.store === null || this.saving) {
      return;
    }
    if (!this.store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      return;
    }

    const deadline = Date.now() + AUTO_SAVE_DELAY_MS;
    this.pending = true;
    this.remainingMs = AUTO_SAVE_DELAY_MS;
    this.countdownTimer = setInterval(() => {
      const left = deadline - Date.now();
      if (left > 0) {
        this.remainingMs = left;
        return;
      }
      this.stopCountdown();
      this.performAutoSave();
    }, AUTO_SAVE_TICK_MS);
  }

  /** 倒计时到点：保存当前输入。 */
  private async performAutoSave(): Promise<void> {
    if (this.store === null || this.saving) {
      return;
    }
    const store = this.store;
    if (!store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      return;
    }
    this.saving = true;
    const item = await store.saveEdits(this.draftContent, this.draftTitle);
    this.saving = false;
    if (item !== null) {
      this.setMessage(`已自动保存：${item.title}`);
      this.syncFromStore();
      // 保存期间用户可能又改了内容——那期间的 @Watch 因 saving=true 被跳过，
      // 这里补一次：仍有未保存改动就重新计时。
      this.restartCountdown();
    } else {
      // ⚠️ 失败后**不**重启计时：否则服务端不可用时会每 2 秒重试一次，无限刷屏。
      // 用户继续输入会自然重新计时，或点「保存」手动重试。
      this.setMessage(store.errorMessage, true);
      this.syncFromStore();
    }
  }

  /** 倒计时状态的文字说明。 */
  private autoSaveStatusText(): string {
    if (!this.autoSave) {
      return '自动保存已关闭';
    }
    if (this.saving) {
      return '保存中…';
    }
    if (this.draftContent.trim().length === 0) {
      return '等待输入';
    }
    if (this.pending) {
      return `${Math.ceil(this.remainingMs / 1000)} 秒后自动保存`;
    }
    if (this.store !== null && this.store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      return '待保存';
    }
    return '已保存';
  }

  // ---- 保存 / 编辑 ----

  /** 手动保存（「保存」按钮 / 收起输入）。 */
  private async submitDraft(): Promise<void> {
    if (this.store === null || this.saving) {
      return;
    }
    if (this.draftContent.trim().length === 0) {
      this.setMessage('内容为空，未保存', true);
      return;
    }
    const store = this.store;
    this.stopCountdown();
    this.saving = true;
    const item = await store.saveEdits(this.draftContent, this.draftTitle);
    this.saving = false;
    if (item !== null) {
      this.setMessage(`已保存：${item.title}`);
      this.draftContent = '';
      this.draftTitle = '';
      this.showInput = false;
      // 显式保存后解除关联，下次输入另起一条
      store.startNew();
      this.editingId = '';
      this.editingTitle = '';
    } else {
      this.setMessage(store.errorMessage, true);
    }
    this.syncFromStore();
  }

  /**
   * 点列表项 → 载入到输入区编辑。
   *
   * ⚠️ 顺序：先把当前未保存的输入落盘，再切换编辑目标。
   * 否则输入框里那几个还没到自动保存时机的字会丢掉。
   */
  private async startEditing(item: ClipboardItem): Promise<void> {
    if (this.store === null) {
      return;
    }
    const store = this.store;
    this.stopCountdown();

    if (store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      await store.saveEdits(this.draftContent, this.draftTitle);
    }

    // 先让 store 记录"已保存内容"，再填输入框，
    // 这样 @Watch 触发时 hasUnsavedChanges 为 false，不会立刻倒计时
    store.loadForEdit(item);
    this.editingId = item.id;
    this.editingTitle = item.title;
    this.draftTitle = item.title;
    this.draftContent = item.content;
    this.showInput = true;
    this.setMessage(`正在编辑：${item.title}`);
    this.syncFromStore();
  }

  /** 解除编辑关联，改为新建。 */
  private handleStartNew(): void {
    this.stopCountdown();
    if (this.store !== null) {
      this.store.startNew();
    }
    this.draftTitle = '';
    this.draftContent = '';
    this.editingId = '';
    this.editingTitle = '';
    this.setMessage('已开启新记录，之后输入的内容会另起一条');
  }

  private clearDraft(): void {
    this.stopCountdown();
    this.draftTitle = '';
    this.draftContent = '';
    this.setMessage('已清空输入');
  }

  // ---- 搜索与排序 ----

  private async doSearch(): Promise<void> {
    if (this.store === null) {
      return;
    }
    await this.store.setSearch(this.searchInput);
    this.setMessage(
      this.store.search.length > 0 ? `已按「${this.store.search}」筛选` : '已清除筛选',
    );
    this.syncFromStore();
  }

  private async clearSearch(): Promise<void> {
    this.searchInput = '';
    await this.doSearch();
  }

  private async toggleOrder(): Promise<void> {
    if (this.store === null) {
      return;
    }
    const next: SortOrder = this.order === SortOrder.DESC ? SortOrder.ASC : SortOrder.DESC;
    await this.store.setOrder(next);
    this.setMessage(next === SortOrder.DESC ? '已切换为最新优先' : '已切换为最早优先');
    this.syncFromStore();
  }

  // ---- 列表项操作 ----

  private isExpanded(id: string): boolean {
    return this.expandedIds.includes(id);
  }

  private toggleExpanded(id: string): void {
    if (this.isExpanded(id)) {
      this.expandedIds = this.expandedIds.filter((item: string) => item !== id);
    } else {
      this.expandedIds = this.expandedIds.concat([id]);
    }
  }

  private shownContent(item: ClipboardItem): string {
    if (item.content.length > COLLAPSE_LENGTH && !this.isExpanded(item.id)) {
      return `${item.content.substring(0, COLLAPSE_LENGTH)}…`;
    }
    return item.content;
  }

  /** 手动读取系统剪贴板并上传。 */
  private async syncNow(): Promise<void> {
    if (this.store === null) {
      return;
    }
    this.setMessage('正在读取剪贴板…');
    const store = this.store;
    const text = await store.clipboard.readText();
    if (text.length === 0) {
      this.setMessage(
        store.clipboard.hasReadPermission()
          ? '剪贴板为空或不是文本'
          : '没有剪贴板读取权限，请在系统设置中授予，或改用「新建/粘贴上传」',
        true,
      );
      return;
    }
    const item = await store.upload(text);
    if (item !== null) {
      this.setMessage('已同步剪贴板');
    } else {
      this.setMessage(store.errorMessage, true);
    }
    this.syncFromStore();
  }

  private async copyItem(item: ClipboardItem): Promise<void> {
    if (this.store === null) {
      return;
    }
    const ok = await this.store.copyToClipboard(item.content);
    this.setMessage(ok ? '已复制到剪贴板' : '复制失败', !ok);
  }

  private async removeItem(item: ClipboardItem): Promise<void> {
    if (this.store === null) {
      return;
    }
    await this.store.remove(item.id);
    this.setMessage('已删除');
    this.syncFromStore();
  }

  /** 删除前二次确认（删数据不可撤销）。 */
  private confirmRemove(item: ClipboardItem): void {
    AlertDialog.show({
      title: '删除记录',
      message: `确定删除「${item.title}」吗？`,
      autoCancel: true,
      primaryButton: {
        value: '取消',
        action: () => {},
      },
      secondaryButton: {
        value: '删除',
        fontColor: Color.Red,
        action: () => {
          this.removeItem(item);
        },
      },
    });
  }

  private async clearAll(): Promise<void> {
    if (this.store === null) {
      return;
    }
    await this.store.clearAll();
    this.expandedIds = [];
    this.setMessage('已清空全部记录');
    this.syncFromStore();
  }

  /** 清空前二次确认（会删掉该用户全部记录）。 */
  private confirmClearAll(): void {
    if (this.total === 0) {
      this.setMessage('暂无记录可清空', true);
      return;
    }
    AlertDialog.show({
      title: '清空全部',
      message: `确定删除全部 ${this.total} 条记录吗？此操作不可撤销。`,
      autoCancel: true,
      primaryButton: {
        value: '取消',
        action: () => {},
      },
      secondaryButton: {
        value: '清空',
        fontColor: Color.Red,
        action: () => {
          this.clearAll();
        },
      },
    });
  }

  private onLogout(): void {
    if (this.store === null) {
      return;
    }
    this.stopCountdown();
    this.store.logout();
    this.searchInput = '';
    this.search = '';
    this.order = SortOrder.DESC;
    this.expandedIds = [];
    this.draftTitle = '';
    this.draftContent = '';
    this.showInput = false;
    this.editingId = '';
    this.editingTitle = '';
    router.replaceUrl({ url: 'pages/LoginPage' }).catch(() => {});
  }

  /** 把 ISO 8601 UTC 字符串转成本地可读时间。 */
  private formatTime(iso: string): string {
    try {
      const date = new Date(iso);
      const pad = (n: number): string => (n < 10 ? `0${n}` : `${n}`);
      return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    } catch (error) {
      return iso;
    }
  }

  @Builder
  itemCard(item: ClipboardItem) {
    Column({ space: 6 }) {
      // 可点击区域：标题 + 内容 → 载入右侧编辑。
      // 只让这一块可点，操作按钮留在外面，避免点「复制」也触发编辑。
      Column({ space: 6 }) {
        Row() {
          Text(this.editingId === item.id ? `● ${item.title}` : item.title)
            .fontSize(14)
            .fontWeight(FontWeight.Bold)
            .fontColor(this.editingId === item.id ? '#1A6FEE' : '#1F2328')
            .layoutWeight(1)
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(this.formatTime(item.updated_at))
            .fontSize(11)
            .fontColor('#999999')
        }
        .width('100%')

        Text(this.shownContent(item))
          .fontSize(12)
          .fontColor('#444444')
          .maxLines(this.isExpanded(item.id) ? 50 : 4)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
          .width('100%')
      }
      .width('100%')
      .onClick(() => {
        this.startEditing(item);
      })

      Row({ space: 10 }) {
        Button('复制')
          .fontSize(12)
          .height(28)
          .onClick(() => {
            this.copyItem(item);
          })
        if (item.content.length > COLLAPSE_LENGTH) {
          Button(this.isExpanded(item.id) ? '收起' : '展开')
            .fontSize(12)
            .height(28)
            .backgroundColor('#EEEEEE')
            .fontColor('#333333')
            .onClick(() => {
              this.toggleExpanded(item.id);
            })
        }
        Button('删除')
          .fontSize(12)
          .height(28)
          .backgroundColor('#FFEEEE')
          .fontColor(Color.Red)
          .onClick(() => {
            this.confirmRemove(item);
          })
      }
      .width('100%')
      .justifyContent(FlexAlign.End)
    }
    .width('100%')
    .padding(12)
    .backgroundColor(this.editingId === item.id ? '#EFF6FF' : Color.White)
    .borderRadius(8)
    .border({
      width: this.editingId === item.id ? 2 : 1,
      color: this.editingId === item.id ? '#1A6FEE' : '#EEEEEE',
    })
  }

  @Builder
  inputPanel() {
    Column({ space: 8 }) {
      // 正在编辑已有记录：必须明确提示，否则用户不知道保存会改掉历史记录
      if (this.editingId.length > 0) {
        Row({ space: 8 }) {
          Text(`✎ 正在编辑：${this.editingTitle}`)
            .fontSize(11)
            .fontColor('#1E40AF')
            .layoutWeight(1)
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Button('改为新建')
            .fontSize(11)
            .height(26)
            .backgroundColor('#FFFFFF')
            .fontColor('#1E40AF')
            .onClick(() => {
              this.handleStartNew();
            })
        }
        .width('100%')
        .padding({ left: 8, right: 8, top: 6, bottom: 6 })
        .backgroundColor('#EFF6FF')
        .borderRadius(6)
        .border({ width: 1, color: '#BFDBFE' })
      }

      TextInput({ placeholder: '标题（可留空，服务端会自动生成）', text: this.draftTitle })
        .fontSize(13)
        .enabled(!this.saving)
        .onChange((value: string) => {
          this.draftTitle = value;
        })
      TextArea({ placeholder: '在这里输入或粘贴内容，停止输入后会自动保存', text: this.draftContent })
        .fontSize(13)
        .height(110)
        .enabled(!this.saving)
        .onChange((value: string) => {
          this.draftContent = value;
        })

      // 自动保存开关 + 倒计时
      Row({ space: 8 }) {
        Toggle({ type: ToggleType.Switch, isOn: this.autoSave })
          .onChange((isOn: boolean) => {
            this.autoSave = isOn;
            if (isOn) {
              this.restartCountdown();
            } else {
              this.stopCountdown();
            }
          })
        Text(`自动保存（停止输入 ${AUTO_SAVE_DELAY_MS / 1000} 秒后）`)
          .fontSize(11)
          .fontColor('#666666')
          .layoutWeight(1)
        Text(this.autoSaveStatusText())
          .fontSize(11)
          .fontColor(this.pending || this.saving ? '#B45309' : '#0A8F4D')
      }
      .width('100%')

      Row({ space: 8 }) {
        Button(this.saving ? '保存中…' : '保存')
          .fontSize(13)
          .height(34)
          .layoutWeight(1)
          .enabled(!this.saving && this.draftContent.trim().length > 0)
          .onClick(() => {
            this.submitDraft();
          })
        Button('新建')
          .fontSize(13)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            this.handleStartNew();
          })
        Button('清空输入')
          .fontSize(13)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .enabled(this.draftContent.length > 0 || this.draftTitle.length > 0)
          .onClick(() => {
            this.clearDraft();
          })
      }
      .width('100%')
    }
    .width('100%')
    .padding(12)
    .backgroundColor(Color.White)
    .borderRadius(8)
    .border({ width: 1, color: '#EEEEEE' })
  }

  build() {
    Column() {
      // ---- 头部：用户 + 连接状态 + 退出 ----
      Row() {
        Column({ space: 2 }) {
          Text(`云剪贴板 · ${this.username}`).fontSize(16).fontWeight(FontWeight.Bold)
          Text(this.realtimeConnected ? '实时同步中' : '实时连接断开，正在重连…')
            .fontSize(11)
            .fontColor(this.realtimeConnected ? '#0A8F4D' : '#B45309')
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)

        Button('退出')
          .fontSize(12)
          .height(30)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            this.onLogout();
          })
      }
      .width('100%')
      .padding({ bottom: 10 })

      // ---- 手动输入上传（无剪贴板权限时的唯一入口）----
      Row({ space: 8 }) {
        Button(this.showInput ? '收起输入' : '＋ 新建 / 粘贴上传')
          .fontSize(13)
          .height(32)
          .layoutWeight(1)
          .onClick(() => {
            this.showInput = !this.showInput;
          })
      }
      .width('100%')

      if (this.showInput) {
        Column() {
          this.inputPanel();
        }
        .padding({ top: 8 })
      }

      // ---- 搜索 ----
      Row({ space: 8 }) {
        TextInput({ placeholder: '搜索标题或内容', text: this.searchInput })
          .fontSize(13)
          .layoutWeight(1)
          .onChange((value: string) => {
            this.searchInput = value;
          })
          .onSubmit(() => {
            this.doSearch();
          })
        Button('搜索')
          .fontSize(13)
          .height(34)
          .onClick(() => {
            this.doSearch();
          })
        if (this.search.length > 0) {
          Button('清除')
            .fontSize(13)
            .height(34)
            .backgroundColor('#EEEEEE')
            .fontColor('#333333')
            .onClick(() => {
              this.clearSearch();
            })
        }
      }
      .width('100%')
      .padding({ top: 8 })

      // ---- 操作区 ----
      Row({ space: 8 }) {
        Button(this.order === SortOrder.DESC ? '最新优先' : '最早优先')
          .fontSize(13)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            this.toggleOrder();
          })
        Button('同步剪贴板')
          .fontSize(13)
          .height(34)
          .layoutWeight(1)
          .onClick(() => {
            this.syncNow();
          })
        Button('清空全部')
          .fontSize(13)
          .height(34)
          .backgroundColor('#FFEEEE')
          .fontColor(Color.Red)
          .onClick(() => {
            this.confirmClearAll();
          })
      }
      .width('100%')
      .padding({ top: 8 })

      if (this.message.length > 0) {
        Text(this.message)
          .fontSize(12)
          .fontColor(this.isError ? Color.Red : '#0A8F4D')
          .width('100%')
          .padding({ top: 8 })
      }

      Text(`共 ${this.total} 条 · 监听${this.monitoring ? '已开启' : '未开启'} · 点条目内容可载入编辑`)
        .fontSize(11)
        .fontColor('#888888')
        .width('100%')
        .padding({ top: 6, bottom: 6 })

      // ---- 列表 ----
      if (this.loading && this.items.length === 0) {
        Text('加载中…').fontSize(13).fontColor('#888888').padding(20)
      } else if (this.items.length === 0) {
        Text(
          this.search.length > 0
            ? `没有匹配「${this.search}」的记录`
            : '暂无记录：点「＋ 新建 / 粘贴上传」输入内容（停止输入会自动保存），或复制一段文字后点「同步剪贴板」',
        )
          .fontSize(13)
          .fontColor('#888888')
          .padding(20)
      } else {
        List({ space: 8 }) {
          ForEach(this.items, (item: ClipboardItem) => {
            ListItem() {
              this.itemCard(item)
            }
          }, (item: ClipboardItem) => item.id)
        }
        .layoutWeight(1)
        .width('100%')

        // ---- 分页 ----
        if (this.pages > 1) {
          Row({ space: 16 }) {
            Button('上一页')
              .fontSize(12)
              .height(28)
              .enabled(this.page > 1)
              .onClick(() => {
                if (this.store !== null && this.page > 1) {
                  this.store.setPage(this.page - 1).then(() => this.syncFromStore());
                }
              })
            Text(`${this.page} / ${this.pages}`).fontSize(12)
            Button('下一页')
              .fontSize(12)
              .height(28)
              .enabled(this.page < this.pages)
              .onClick(() => {
                if (this.store !== null && this.page < this.pages) {
                  this.store.setPage(this.page + 1).then(() => this.syncFromStore());
                }
              })
          }
          .padding({ top: 8 })
        }
      }
    }
    .width('100%')
    .height('100%')
    .padding(16)
    .backgroundColor('#F5F6F8')
  }
}