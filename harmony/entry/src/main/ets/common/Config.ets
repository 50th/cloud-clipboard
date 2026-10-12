/**
 * 应用级配置。
 *
 * ⚠️ **后端地址需要按运行环境调整**（这是鸿蒙端最容易卡住的一步）：
 *
 * | 运行环境 | 应填的地址 | 原因 |
 * |---------|-----------|------|
 * | 真机（与电脑同一局域网） | `http://<电脑局域网IP>:8000` | 手机访问的是电脑，不是自己 |
 * | HarmonyOS 模拟器 | 见下方说明 | 模拟器内的 `127.0.0.1` 指向模拟器自身 |
 * | 在设备上跑后端（不可能） | —— | —— |
 *
 * 另外**后端必须监听 `0.0.0.0`**，只监听 `127.0.0.1` 时任何设备都连不上：
 * ```
 * uvicorn app.main:app --host 0.0.0.0 --port 8000
 * ```
 * 并且要把设备的来源加进后端 `CORS_ORIGINS`。
 */
import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';

/** 后端基址。**真机调试时改成电脑的局域网 IP。** */
export const DEFAULT_API_BASE_URL: string = 'http://192.168.3.54:8000';

/** API 前缀，与后端 `API_V1_PREFIX` 一致。 */
export const API_PREFIX: string = '/api/v1';

/** 请求超时（毫秒）。 */
export const REQUEST_TIMEOUT_MS: number = 10_000;

/** WebSocket 心跳间隔（毫秒），与 `docs/ws-protocol.md` 一致。 */
export const WS_HEARTBEAT_MS: number = 30_000;

/** 重连退避上限（毫秒），与 `docs/ws-protocol.md` 一致。 */
export const WS_BACKOFF_MAX_MS: number = 30_000;

const PREFERENCES_NAME = 'cloud_clipboard';
const KEY_API_BASE_URL = 'api_base_url';
const KEY_TOKEN = 'access_token';

function preferenceStore(context: common.Context): preferences.Preferences {
  return preferences.getPreferencesSync(context, { name: PREFERENCES_NAME });
}

/** 读取后端基址（可在设置里改过）。 */
export function loadApiBaseUrl(context: common.Context): string {
  try {
    const store = preferenceStore(context);
    return store.getSync(KEY_API_BASE_URL, DEFAULT_API_BASE_URL) as string;
  } catch (error) {
    return DEFAULT_API_BASE_URL;
  }
}

/** 保存后端基址。 */
export function saveApiBaseUrl(context: common.Context, url: string): void {
  const store = preferenceStore(context);
  store.putSync(KEY_API_BASE_URL, url.trim());
  store.flush();
}

/** 读取本地保存的 JWT。 */
export function loadToken(context: common.Context): string {
  try {
    const store = preferenceStore(context);
    return store.getSync(KEY_TOKEN, '') as string;
  } catch (error) {
    return '';
  }
}

/** 保存 / 清除 JWT（传空字符串即清除）。 */
export function saveToken(context: common.Context, token: string): void {
  const store = preferenceStore(context);
  store.putSync(KEY_TOKEN, token);
  store.flush();
}
