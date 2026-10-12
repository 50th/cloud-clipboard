/**
 * 登录 / 注册页。
 *
 * 后端已接入真实 JWT：未登录时所有剪贴板接口返回 401，
 * 因此这里没有"演示用户"兜底入口。
 */
import { common } from '@kit.AbilityKit';
import { router } from '@kit.ArkUI';

import { AppStore } from '../common/AppStore';
import { loadApiBaseUrl } from '../common/Config';

@Entry
@Component
struct LoginPage {
  @State username: string = '';
  @State email: string = '';
  @State password: string = '';
  @State isRegister: boolean = false;
  @State submitting: boolean = false;
  @State errorMessage: string = '';
  @State infoMessage: string = '';
  @State baseUrl: string = '';

  private store: AppStore | null = null;
  private context: common.UIAbilityContext | null = null;

  aboutToAppear(): void {
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    this.store = AppStore.get(this.context);
    this.baseUrl = loadApiBaseUrl(this.context);

    // 已有有效令牌则直接进入列表页，不必重复登录
    if (this.store.isLoggedIn) {
      this.store.restoreSession().then(() => {
        if (this.store !== null && this.store.isLoggedIn) {
          this.goToList();
        }
      });
    }
  }

  private goToList(): void {
    router.replaceUrl({ url: 'pages/ClipboardPage' }).catch(() => {
      this.errorMessage = '页面跳转失败';
    });
  }

  /**
   * 保存后端地址（真机/换网络时无需改代码重编译）。
   *
   * 只做前缀校验：地址是否真的可达由登录请求给出答案，
   * 在这里做过多校验反而会挡掉合法的内网地址。
   */
  private saveBaseUrl(): void {
    const url = this.baseUrl.trim();
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      this.errorMessage = '地址需以 http:// 或 https:// 开头';
      this.infoMessage = '';
      return;
    }
    const store = this.store;
    if (store !== null) {
      store.setBaseUrl(url);
      this.baseUrl = store.baseUrl;
    } else {
      this.baseUrl = url;
    }
    this.errorMessage = '';
    this.infoMessage = '后端地址已保存';
  }

  private canSubmit(): boolean {
    if (this.submitting) {
      return false;
    }
    if (this.username.trim().length < 3 || this.password.length < 6) {
      return false;
    }
    if (this.isRegister && this.email.trim().length < 3) {
      return false;
    }
    return true;
  }

  private async submit(): Promise<void> {
    if (!this.canSubmit() || this.store === null) {
      return;
    }
    this.submitting = true;
    this.errorMessage = '';
    const store = this.store;

    const ok: boolean = this.isRegister
      ? await store.register(this.username.trim(), this.email.trim(), this.password)
      : await store.login(this.username.trim(), this.password);

    this.submitting = false;
    if (ok) {
      this.password = '';
      this.goToList();
    } else {
      // store 内部已把可读原因放进 errorMessage
      this.errorMessage = store.errorMessage;
    }
  }

  build() {
    Column({ space: 12 }) {
      Text('云剪贴板').fontSize(28).fontWeight(FontWeight.Bold)

      Row({ space: 8 }) {
        Button('登录')
          .type(this.isRegister ? ButtonType.Normal : ButtonType.Capsule)
          .backgroundColor(this.isRegister ? '#EEEEEE' : '#1A6FEE')
          .fontColor(this.isRegister ? '#333333' : Color.White)
          .onClick(() => {
            this.isRegister = false;
          })
        Button('注册')
          .type(this.isRegister ? ButtonType.Capsule : ButtonType.Normal)
          .backgroundColor(this.isRegister ? '#1A6FEE' : '#EEEEEE')
          .fontColor(this.isRegister ? Color.White : '#333333')
          .onClick(() => {
            this.isRegister = true;
          })
      }
      .width('100%')
      .justifyContent(FlexAlign.Center)

      TextInput({ placeholder: this.isRegister ? '用户名（3-32 字符）' : '用户名或邮箱', text: this.username })
        .onChange((value: string) => {
          this.username = value;
        })
        .enabled(!this.submitting)

      if (this.isRegister) {
        TextInput({ placeholder: '邮箱', text: this.email })
          .type(InputType.Email)
          .onChange((value: string) => {
            this.email = value;
          })
          .enabled(!this.submitting)
      }

      TextInput({ placeholder: '密码（至少 6 字符）', text: this.password })
        .type(InputType.Password)
        .onChange((value: string) => {
          this.password = value;
        })
        .enabled(!this.submitting)

      Button(this.submitting ? '提交中…' : (this.isRegister ? '注册并登录' : '登录'))
        .width('100%')
        .enabled(this.canSubmit())
        .onClick(() => {
          this.submit();
        })

      if (this.errorMessage.length > 0) {
        Text(this.errorMessage)
          .fontSize(12)
          .fontColor(Color.Red)
          .width('100%')
      }

      if (this.infoMessage.length > 0) {
        Text(this.infoMessage)
          .fontSize(12)
          .fontColor('#0A8F4D')
          .width('100%')
      }

      Text('后端地址（真机调试改成电脑的局域网 IP，并让后端监听 0.0.0.0）')
        .fontSize(11)
        .fontColor('#666666')
        .width('100%')

      Row({ space: 8 }) {
        TextInput({ placeholder: 'http://192.168.1.10:8000', text: this.baseUrl })
          .fontSize(12)
          .layoutWeight(1)
          .enabled(!this.submitting)
          .onChange((value: string) => {
            this.baseUrl = value;
          })
        Button('保存')
          .fontSize(12)
          .height(34)
          .backgroundColor('#EEEEEE')
          .fontColor('#333333')
          .enabled(!this.submitting)
          .onClick(() => {
            this.saveBaseUrl();
          })
      }
      .width('100%')
    }
    .width('100%')
    .height('100%')
    .padding(24)
    .justifyContent(FlexAlign.Center)
  }
}
