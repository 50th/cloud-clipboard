/**
 * 编辑页（独立页面）。
 *
 * 与列表页分工：**列表页只负责浏览/搜索/复制/删除，本页只负责编辑一条记录**。
 * 拆开的原因：编辑页有自己的输入状态、倒计时与保存中状态，混在列表页里时
 * 两者会互相干扰（列表刷新、剪贴板监听、搜索都会影响同一个页面的状态）。
 */

import { common } from '@kit.AbilityKit';
import { router } from '@kit.ArkUI';

import { AppStore } from '../common/AppStore';
import { EditRouteParams, ROUTE_LOGIN } from '../common/Routes';
import { ClipboardItem } from '../models/Types';

/** 自动保存：停止输入多久后保存（毫秒）。与 Web 端一致的 2 秒。 */
const AUTO_SAVE_DELAY_MS: number = 2000;
/** 倒计时刷新间隔（毫秒）。200ms 足够让秒数看起来连续。 */
const AUTO_SAVE_TICK_MS: number = 200;

@Entry
@Component
struct EditPage {
  @State draftTitle: string = '';
  @State draftContent: string = '';
  /** 自动保存开关 */
  @State autoSave: boolean = true;
  /** 倒计时剩余毫秒（0 表示未在计时） */
  @State remainingMs: number = 0;
  /** 是否有未保存改动（倒计时进行中） */
  @State pending: boolean = false;
  /** 是否正在保存 */
  @State saving: boolean = false;
  /** 是否正在载入已有记录 */
  @State loading: boolean = false;
  @State message: string = '';
  @State isError: boolean = false;
  /** 正在编辑的记录 id；空串表示新建 */
  @State editingId: string = '';
  /** 正在编辑的记录标题（仅用于提示） */
  @State editingTitle: string = '';

  private store: AppStore | null = null;
  /** 倒计时计时器句柄 */
  private countdownTimer: number = -1;

  aboutToAppear(): void {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = AppStore.get(context);

    if (!this.store.isLoggedIn) {
      router.replaceUrl({ url: ROUTE_LOGIN }).catch(() => {});
      return;
    }

    const params = router.getParams() as EditRouteParams;
    const itemId: string = params !== undefined && params !== null ? (params.id ?? '') : '';

    if (itemId.length > 0) {
      this.loadExisting(itemId);
    } else {
      // 新建：解除上一轮的编辑关联
      this.store.startNew();
      this.editingId = '';
      this.editingTitle = '';
      this.setMessage('新记录：输入内容后会自动保存');
    }
  }

  aboutToDisappear(): void {
    this.stopCountdown();
    // 兜底：用系统返回手势离开时也尽量把未保存内容落盘。
    // 这里不能 await（页面正在销毁），但 store 是单例，请求会继续完成。
    if (this.store !== null && this.store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      this.store.saveEdits(this.draftContent, this.draftTitle).catch(() => {});
    }
  }

  private setMessage(text: string, isError: boolean = false): void {
    this.message = text;
    this.isError = isError;
  }

  /** 载入已有记录（取**最新**内容，而不是列表里的旧快照）。 */
  private async loadExisting(itemId: string): Promise<void> {
    if (this.store === null) {
      return;
    }
    const store = this.store;
    this.loading = true;
    try {
      const item = await store.api.getItem(itemId);
      store.loadForEdit(item);
      this.editingId = item.id;
      this.editingTitle = item.title;
      this.draftTitle = item.title;
      this.draftContent = item.content;
      this.stopCountdown();
      this.setMessage('已载入，可直接编辑');
    } catch (error) {
      // 记录可能已在别处被删除
      store.startNew();
      this.editingId = '';
      this.editingTitle = '';
      this.setMessage('载入失败：该记录可能已被删除', true);
    } finally {
      this.loading = false;
    }
  }

  // ---- 自动保存倒计时 ----

  private stopCountdown(): void {
    if (this.countdownTimer !== -1) {
      clearInterval(this.countdownTimer);
      this.countdownTimer = -1;
    }
    this.pending = false;
    this.remainingMs = 0;
  }

  /**
   * 安排一次自动保存。
   *
   * ⚠️ **由输入回调显式调用，不用 `@Watch` 装饰器。**
   * `@Watch` 一旦没如期触发，倒计时就完全不会启动，而且不会报任何错——
   * 表现为"自动保存压根没生效"，极难排查。
   * 显式调用是确定性的：只要 onChange 到了，就一定安排上了。
   */
  private scheduleAutoSave(): void {
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

  /** 倒计时到点：保存。 */
  private async performAutoSave(): Promise<void> {
    if (this.store === null || this.saving) {
      return;
    }
    const store = this.store;
    if (!store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      return;
    }

    this.saving = true;
    let item: ClipboardItem | null = null;
    try {
      item = await store.saveEdits(this.draftContent, this.draftTitle);
    } finally {
      // ⚠️ 必须在 finally 里复位：一旦 saving 卡在 true，
      // scheduleAutoSave 会永久提前返回，自动保存就彻底静默失效了。
      this.saving = false;
    }

    if (item !== null) {
      // 新建记录保存成功后也进入「编辑」态：后续保存继续更新同一条
      this.editingId = item.id;
      this.editingTitle = item.title;
      this.setMessage(`已自动保存：${item.title}`);
      // 保存期间用户可能又改了内容（那时的调用因 saving=true 被跳过），这里补一次
      this.scheduleAutoSave();
    } else {
      // ⚠️ 失败后**不**重新计时：否则服务端不可用时会每 2 秒重试一次，无限刷屏
      this.setMessage(store.errorMessage, true);
    }
  }

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

  // ---- 手动操作 ----

  /** 立即保存。 */
  private async saveNow(): Promise<void> {
    if (this.store === null || this.saving) {
      return;
    }
    if (this.draftContent.trim().length === 0) {
      this.setMessage('内容为空，无法保存', true);
      return;
    }
    const store = this.store;
    this.stopCountdown();
    this.saving = true;
    let item: ClipboardItem | null = null;
    try {
      item = await store.saveEdits(this.draftContent, this.draftTitle);
    } finally {
      this.saving = false;
    }
    if (item !== null) {
      // 新建记录保存成功后也进入「编辑」态：后续保存继续更新同一条
      this.editingId = item.id;
      this.editingTitle = item.title;
      this.setMessage(`已保存：${item.title}`);
    } else {
      this.setMessage(store.errorMessage, true);
    }
  }

  /** 保存并返回列表。 */
  private async saveAndBack(): Promise<void> {
    if (this.store !== null && this.store.hasUnsavedChanges(this.draftContent, this.draftTitle)) {
      await this.saveNow();
    } else {
      this.stopCountdown();
    }
    router.back();
  }

  /** 改为新建（解除对已有记录的关联）。 */
  private handleStartNew(): void {
    this.stopCountdown();
    if (this.store !== null) {
      this.store.startNew();
    }
    this.draftTitle = '';
    this.draftContent = '';
    this.editingId = '';
    this.editingTitle = '';
    this.setMessage('已改为新建，之后保存会另起一条');
  }

  private clearInput(): void {
    this.stopCountdown();
    this.draftTitle = '';
    this.draftContent = '';
    this.setMessage('已清空输入');
  }

  build() {
    Column() {
      // ---- 头部 ----
      Row() {
        Button('← 返回')
          .fontSize(13)
          .height(32)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .onClick(() => {
            this.saveAndBack();
          })
        Column({ space: 2 }) {
          Text(this.editingId.length > 0 ? '编辑记录' : '新建记录')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .width('100%')
            .textAlign(TextAlign.Center)
          Text(this.editingId.length > 0 ? this.editingTitle : '停止输入后自动保存')
            .fontSize(11)
            .fontColor('#666666')
            .maxLines(1)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
            .width('100%')
            .textAlign(TextAlign.Center)
        }
        .layoutWeight(1)

        Button(this.saving ? '保存中…' : '保存')
          .fontSize(13)
          .height(32)
          .enabled(!this.saving && this.draftContent.trim().length > 0)
          .onClick(() => {
            this.saveNow();
          })
      }
      .width('100%')
      .padding({ bottom: 12 })

      if (this.loading) {
        Text('载入中…').fontSize(13).fontColor('#888888').padding(20)
      } else {
        // ---- 标题 ----
        Column({ space: 4 }) {
          Text('标题（留空则自动生成）').fontSize(11).fontColor('#666666').width('100%')
          TextInput({ placeholder: '不填也可以', text: this.draftTitle })
            .fontSize(13)
            .enabled(!this.saving)
            .onChange((value: string) => {
              this.draftTitle = value;
              // 显式安排自动保存（不依赖 @Watch）
              this.scheduleAutoSave();
            })
        }
        .width('100%')

        // ---- 内容 ----
        Column({ space: 4 }) {
          Text(`内容（${this.draftContent.length} 字）`).fontSize(11).fontColor('#666666').width('100%')
          TextArea({ placeholder: '在这里输入或粘贴内容', text: this.draftContent })
            .fontSize(13)
            .layoutWeight(1)
            .width('100%')
            .enabled(!this.saving)
            .onChange((value: string) => {
              this.draftContent = value;
              // 显式安排自动保存（不依赖 @Watch）
              this.scheduleAutoSave();
            })
        }
        .width('100%')
        .layoutWeight(1)

        // ---- 自动保存开关 + 倒计时 ----
        Row({ space: 8 }) {
          Toggle({ type: ToggleType.Switch, isOn: this.autoSave })
            .onChange((isOn: boolean) => {
              this.autoSave = isOn;
              if (isOn) {
                this.scheduleAutoSave();
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
        .padding({ top: 8 })

        // ---- 其他操作 ----
        Row({ space: 8 }) {
          Button('改为新建')
            .fontSize(13)
            .height(34)
            .backgroundColor('#EEEEEE')
            .fontColor('#333333')
            .enabled(this.editingId.length > 0)
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
              this.clearInput();
            })
        }
        .width('100%')
        .padding({ top: 8 })
      }

      if (this.message.length > 0) {
        Text(this.message)
          .fontSize(12)
          .fontColor(this.isError ? Color.Red : '#0A8F4D')
          .width('100%')
          .padding({ top: 8 })
      }
    }
    .width('100%')
    .height('100%')
    .padding(16)
    .backgroundColor('#F5F6F8')
  }
}
