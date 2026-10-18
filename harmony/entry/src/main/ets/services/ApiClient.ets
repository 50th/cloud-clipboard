/**
 * 后端 API 客户端。
 *
 * 对应 REST 接口见 `docs/api.md`。所有请求自动附带 `Authorization: Bearer <JWT>`。
 *
 * ⚠️ 关于后端地址：设备上的 `127.0.0.1` 指向**设备自己**，不是你的电脑。
 * 真机调试请把 `common/Config.ets` 的地址改成电脑局域网 IP，
 * 并让后端监听 `0.0.0.0`。详见该文件的说明。
 */
import { http } from '@kit.NetworkKit';
import { BusinessError } from '@kit.BasicServicesKit';

import {
  API_PREFIX,
  REQUEST_TIMEOUT_MS,
  loadApiBaseUrl,
  loadToken,
} from '../common/Config';
import {
  AuthResponse,
  ClipboardItem,
  ClipboardItemCreate,
  ClipboardItemList,
  ClipboardItemUpdate,
  MessageResponse,
  SortBy,
  SortOrder,
  UserInfo,
} from '../models/Types';

/** 接口调用失败时抛出，`status` 便于上层分支处理（如 401 跳登录）。 */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** 后端错误响应的形状（FastAPI 用 `detail`）。 */
interface ErrorBody {
  detail?: string | object;
}

/**
 * 请求体类型。
 *
 * ⚠️ ArkTS 不允许**无类型的对象字面量**（`arkts-no-untyped-obj-literals`），
 * 所以每个请求体都必须有显式声明的类型，不能用匿名字面量直接传给函数。
 */
interface AuthRequestBody {
  username: string;
  password: string;
}

interface RegisterRequestBody {
  username: string;
  email: string;
  password: string;
}

/** 空响应体的占位类型（删除类接口返回空体）。 */
interface EmptyBody {}

/** 从任意错误体里提取可读提示。 */
function readErrorDetail(body: string): string {
  try {
    const parsed = JSON.parse(body) as ErrorBody;
    const detail: string | object | undefined = parsed.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      // FastAPI 的校验错误是数组，取第一条的 msg
      const list = detail as Record<string, string>[];
      if (list.length > 0) {
        return list[0]['msg'] ?? '请求参数不合法';
      }
    } else if (detail !== undefined) {
      return JSON.stringify(detail);
    }
  } catch (error) {
    // 不是 JSON，落到下面的兜底
  }
  return body.length > 0 ? body : '请求失败';
}

/** 调用后端服务。 */
export class ApiClient {
  private context: Context;
  private baseUrl: string = '';
  private token: string = '';

  constructor(context: Context) {
    this.context = context;
    this.baseUrl = loadApiBaseUrl(context);
    this.token = loadToken(context);
  }

  /** 重新读取配置（改了后端地址或登录后调用）。 */
  refresh(): void {
    this.baseUrl = loadApiBaseUrl(this.context);
    this.token = loadToken(this.context);
  }

  /** 当前使用的后端基址（界面展示用）。 */
  get currentBaseUrl(): string {
    return this.baseUrl;
  }

  /** 是否已登录（本地有令牌）。真正的有效性由服务端判定。 */
  get hasToken(): boolean {
    return this.token.length > 0;
  }

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.token.length > 0) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  /** 发一次请求并解析 JSON；非 2xx 抛 `ApiError`。 */
  private async send<T>(
    method: http.RequestMethod,
    path: string,
    body?: object,
  ): Promise<T> {
    const url = `${this.baseUrl}${API_PREFIX}${path}`;
    const options: http.HttpRequestOptions = {
      method: method,
      header: this.buildHeaders(),
      connectTimeout: REQUEST_TIMEOUT_MS,
      readTimeout: REQUEST_TIMEOUT_MS,
      expectDataType: http.HttpDataType.STRING,
    };
    if (body !== undefined) {
      options.extraData = JSON.stringify(body);
    }

    const request = http.createHttp();
    try {
      const response = await request.request(url, options);
      const status = response.responseCode as number;
      const raw = typeof response.result === 'string' ? response.result : '';

      if (status < 200 || status >= 300) {
        throw new ApiError(status, readErrorDetail(raw));
      }
      // 部分接口（删除类）返回空体，此时给一个空对象即可
      if (raw.length === 0) {
        const empty: EmptyBody = {};
        return empty as T;
      }
      return JSON.parse(raw) as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      const business = error as BusinessError;
      // 连不上、超时等都归到这里，给出比原始错误更可操作的提示
      throw new ApiError(
        0,
        `无法连接后端 ${this.baseUrl}（${business.message ?? '网络错误'}）。` +
          '请确认后端已启动、监听 0.0.0.0，且本机与设备在同一网络。',
      );
    } finally {
      request.destroy();
    }
  }

  // ---- 认证 ----

  /** 注册。成功即返回令牌，无需再登录。 */
  async register(username: string, email: string, password: string): Promise<AuthResponse> {
    const body: RegisterRequestBody = {
      username: username,
      email: email,
      password: password,
    };
    return await this.send<AuthResponse>(http.RequestMethod.POST, '/auth/register', body);
  }

  /** 登录。`username` 支持用户名或邮箱。 */
  async login(username: string, password: string): Promise<AuthResponse> {
    const body: AuthRequestBody = {
      username: username,
      password: password,
    };
    return await this.send<AuthResponse>(http.RequestMethod.POST, '/auth/login', body);
  }

  /** 当前用户。令牌无效时抛 401。 */
  async me(): Promise<UserInfo> {
    return await this.send<UserInfo>(http.RequestMethod.GET, '/auth/me');
  }

  // ---- 剪贴板 ----

  /** 列表：分页 / 搜索 / 排序（固定按**修改时间**排序，见下方注释）。 */
  async listItems(
    page: number = 1,
    size: number = 20,
    order: SortOrder = SortOrder.DESC,
    search?: string,
  ): Promise<ClipboardItemList> {
    // 必须显式传 sort_by：后端默认按 created_at 排，而产品要求"最近修改"在前。
    // 不传的话，编辑一条旧记录后它不会上移，看起来像"没保存成功"。
    let path =
      `/clipboard/items?page=${page}&size=${size}` +
      `&sort_by=${SortBy.UPDATED_AT}&order=${order}`;
    if (search !== undefined && search.length > 0) {
      path += `&search=${encodeURIComponent(search)}`;
    }
    return await this.send<ClipboardItemList>(http.RequestMethod.GET, path);
  }

  /** 详情：按 id 取单条（编辑页据此载入**最新**内容，而不是列表里的旧快照）。 */
  async getItem(id: string): Promise<ClipboardItem> {
    return await this.send<ClipboardItem>(http.RequestMethod.GET, `/clipboard/items/${id}`);
  }

  /**
   * 创建。
   *
   * 服务端**内置内容去重**：相同内容返回同一条记录并刷新 `updated_at`，
   * 不会新建。因此连续同步相同内容不会产生多行。
   */
  async createItem(payload: ClipboardItemCreate): Promise<ClipboardItem> {
    return await this.send<ClipboardItem>(http.RequestMethod.POST, '/clipboard/items', payload);
  }

  /** 更新已有记录（只传要改的字段）。 */
  async updateItem(id: string, payload: ClipboardItemUpdate): Promise<ClipboardItem> {
    return await this.send<ClipboardItem>(
      http.RequestMethod.PATCH,
      `/clipboard/items/${id}`,
      payload,
    );
  }

  /** 删除单条。 */
  async deleteItem(id: string): Promise<MessageResponse> {
    return await this.send<MessageResponse>(
      http.RequestMethod.DELETE,
      `/clipboard/items/${id}`,
    );
  }

  /** 清空全部。 */
  async clearItems(): Promise<MessageResponse> {
    return await this.send<MessageResponse>(http.RequestMethod.DELETE, '/clipboard/items');
  }
}
