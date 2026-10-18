/**
 * 剪贴板列表页。
 *
 * **只负责浏览**：搜索、排序、复制、删除、清空、分页、实时状态；
 * 编辑在独立的编辑页（`pages/EditPage`）里进行，点条目或「＋ 新建」跳过去。
 *
 * 为什么拆开：编辑页有自己的输入状态与自动保存倒计时，混在列表页里时
 * 列表刷新、剪贴板监听、搜索都会干扰同一个页面的状态；分开后各管一摊。
 */

import { common } from '@kit.AbilityKit';
import { router } from '@kit.ArkUI';

import { AppStore } from '../common/AppStore';
import { EditRouteParams, ROUTE_EDIT, ROUTE_LOGIN } from '../common/Routes';
import { ClipboardItem, SortOrder } from '../models/Types';

/** 超过该长度的内容在卡片里折叠显示。与 Web 端 `ClipboardItemCard.vue` 一致。 */
const COLLAPSE_LENGTH: number = 160;

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

  /** 已展开的长内容 id 列表（ArkUI 无法逐项维护状态，统一在此记录） */
  @State expandedIds: string[] = [];

  private store: AppStore | null = null;
  /** 保存监听回调引用，页面销毁时才能正确取消注册 */
  private listener: (() => void) | null = null;

  aboutToAppear(): void {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = AppStore.get(context);

    // 未登录时踢回登录页（例如令牌过期）
    if (!this.store.isLoggedIn) {
      router.replaceUrl({ url: ROUTE_LOGIN }).catch(() => {});
      return;
    }

    const store = this.store;
    this.search = store.search;
    this.order = store.order;
    this.listen();

    store.restoreSession().then(() => {
      this.startMonitor();
    });
  }

  /**
   * 订阅 store 的状态变化（**幂等**）。
   *
   * ⚠️ 为什么不只在 `aboutToAppear` 里订阅：
   * 页面被 `pushUrl` 覆盖时若触发了 `aboutToDisappear`，监听会被退订，
   * 而返回时 `aboutToAppear` **不会**再执行 —— 于是列表永远收不到更新，
   * 表现为"从编辑页返回后列表还是旧的"。所以每次显示都重新订阅一次。
   */
  private listen(): void {
    if (this.store === null) {
      return;
    }
    if (this.listener !== null) {
      this.store.unsubscribe(this.listener);
    }
    this.listener = () => {
      this.syncFromStore();
    };
    this.store.subscribe(this.listener);
  }

  /**
   * 每次本页显示时刷新列表。
   *
   * 从编辑页返回时必然触发：那边可能新建/修改了记录。
   * 这里重新订阅 + 主动拉一次，两条路都走，不依赖某一条一定生效。
   */
  onPageShow(): void {
    if (this.store === null || !this.store.isLoggedIn) {
      return;
    }
    this.listen();
    this.store.refreshItems(true).then(() => this.syncFromStore());
  }

  aboutToDisappear(): void {
    // 必须清理：否则剪贴板监听与 WebSocket 会在页面销毁后继续跑
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
      this.setMessage('未获得剪贴板读取权限：可点「＋ 新建」手动输入，复制功能不受影响', true);
    } else {
      this.setMessage('已开启剪贴板监听：复制内容会自动同步');
    }
    this.syncFromStore();
  }

  // ---- 页面跳转 ----

  /** 打开编辑页编辑某一条。 */
  private openEdit(item: ClipboardItem): void {
    const params: EditRouteParams = { id: item.id };
    router.pushUrl({ url: ROUTE_EDIT, params: params }).catch(() => {
      this.setMessage('打开编辑页失败', true);
    });
  }

  /** 打开编辑页新建一条。 */
  private openNew(): void {
    router.pushUrl({ url: ROUTE_EDIT }).catch(() => {
      this.setMessage('打开编辑页失败', true);
    });
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
    this.setMessage(next === SortOrder.DESC ? '已切换为最近修改在前' : '已切换为最早修改在前');
    this.syncFromStore();
  }

  /** 手动刷新当前页（静默拉取，不闪加载态）。 */
  private async manualRefresh(): Promise<void> {
    if (this.store === null) {
      return;
    }
    await this.store.refreshItems(true);
    this.syncFromStore();
    this.setMessage(`已刷新，共 ${this.store.total} 条`);
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

  /** 手动读取系统剪贴板并上传（新建一条，不影响编辑页正在编辑的内容）。 */
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
          : '没有剪贴板读取权限，请在系统设置中授予，或点「＋ 新建」手动输入',
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
    this.store.logout();
    this.searchInput = '';
    this.search = '';
    this.order = SortOrder.DESC;
    this.expandedIds = [];
    router.replaceUrl({ url: ROUTE_LOGIN }).catch(() => {});
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
      // 可点击区域：标题 + 内容 → 进入编辑页。
      // 只让这一块可点，操作按钮留在外面，避免点「复制」也跳转。
      Column({ space: 6 }) {
        Row() {
          Text(item.title)
            .fontSize(14)
            .fontWeight(FontWeight.Bold)
            .fontColor('#1F2328')
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
        this.openEdit(item);
      })

      Row({ space: 10 }) {
        Button('编辑')
          .fontSize(12)
          .height(28)
          .onClick(() => {
            this.openEdit(item);
          })
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

      // ---- 新建（跳到编辑页）----
      Row({ space: 8 }) {
        Button('＋ 新建')
          .fontSize(13)
          .height(36)
          .layoutWeight(1)
          .onClick(() => {
            this.openNew();
          })
        Button('同步剪贴板')
          .fontSize(13)
          .height(36)
          .layoutWeight(1)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            this.syncNow();
          })
      }
      .width('100%')

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
        Button(this.order === SortOrder.DESC ? '最近修改' : '最早修改')
          .fontSize(13)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .layoutWeight(1)
          .onClick(() => {
            this.toggleOrder();
          })
        Button('刷新')
          .fontSize(13)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .layoutWeight(1)
          .onClick(() => {
            this.manualRefresh();
          })
        Button('清空全部')
          .fontSize(13)
          .height(34)
          .backgroundColor('#FFEEEE')
          .fontColor(Color.Red)
          .layoutWeight(1)
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

      Text(`共 ${this.total} 条 · 监听${this.monitoring ? '已开启' : '未开启'} · 点条目可编辑`)
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
            : '暂无记录：点「＋ 新建」输入内容（停止输入会自动保存），或复制一段文字后点「同步剪贴板」',
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
