/**
 * 页面路由常量与参数契约。
 *
 * 集中一处，改页面名时只改这里；参数用显式 interface（ArkTS 不允许
 * 无类型的对象字面量，传 params 时必须先有类型）。
 */

/** 登录页 */
export const ROUTE_LOGIN: string = 'pages/LoginPage';
/** 剪贴板列表页 */
export const ROUTE_LIST: string = 'pages/ClipboardPage';
/** 编辑页 */
export const ROUTE_EDIT: string = 'pages/EditPage';

/** 编辑页路由参数。 */
export interface EditRouteParams {
  /** 要编辑的记录 id；不传表示新建 */
  id?: string;
}
