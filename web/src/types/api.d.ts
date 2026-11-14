export interface paths {
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 用户注册
         * @description 创建账号并**直接返回令牌**，前端无需再登录一次。
         *
         *     `password` 需至少 8 个字符、同时包含字母和数字、不能包含用户名；上限 72 字节是 bcrypt 的硬限制（超出会抛错，不会被截断）。
         */
        post: operations["register_api_v1_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 用户登录
         * @description `username` 支持用户名或邮箱。凭证错误统一返回 401，不区分是哪一个错。
         */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/change-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 修改密码
         * @description 校验当前密码后更新密码，并使该账号的**全部旧令牌与 WebSocket 连接立即失效**。
         *
         *     新密码需满足：至少 8 个字符、同时包含字母和数字、不能包含用户名、不超过 72 字节（bcrypt 上限）。修改成功后需用新密码重新登录。
         */
        post: operations["change_password_api_v1_auth_change_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 获取当前用户
         * @description 依据 `Authorization: Bearer <token>` 返回对应账号；令牌无效返回 401。
         */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clipboard/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 获取剪贴板列表
         * @description 支持分页、按 `content_type` 筛选、按**标题或内容**关键字搜索与排序。
         */
        get: operations["list_items_api_v1_clipboard_items_get"];
        put?: never;
        /**
         * 创建剪贴板项
         * @description 提交文字内容。`title` 留空时由服务端自动生成（`剪贴板 · <月-日 时:分>`），时间按 `timezone`（IANA 时区名，前端会传浏览器时区）展示，例如 `剪贴板 · 10-05 21:56`。
         *
         *     **已内置内容去重**：同一用户提交相同 `content` 时不创建新记录，只更新 `updated_at`；此时仅当显式传了 `title` 才覆盖标题（去重命中时对应广播 `clipboard.updated`）。
         */
        post: operations["create_item_api_v1_clipboard_items_post"];
        /**
         * 清空剪贴板
         * @description 删除当前用户的全部剪贴板项，并广播 `clipboard.cleared`。
         */
        delete: operations["clear_items_api_v1_clipboard_items_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clipboard/items/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 获取剪贴板详情 */
        get: operations["get_item_api_v1_clipboard_items__id__get"];
        put?: never;
        post?: never;
        /** 删除单条剪贴板项 */
        delete: operations["delete_item_api_v1_clipboard_items__id__delete"];
        options?: never;
        head?: never;
        /**
         * 更新剪贴板项
         * @description 只更新显式传入的字段。
         *
         *     **用途：自动保存复用同一条草稿记录**——打字过程中每隔一段时间保存一次，而不是每个中间态都新建一行。
         *
         *     内容变化且未传 `title` 时，标题会按更新时刻与 `timezone` 重新生成。
         */
        patch: operations["update_item_api_v1_clipboard_items__id__patch"];
        trace?: never;
    };
    "/api/v1/clipboard/items/{id}/shares": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 创建分享
         * @description 为一条文字剪贴板生成受控只读链接。
         *
         *     - `mode=snapshot` 复制当前正文；`mode=live` 跟随原记录最新内容
         *     - 默认有效期 7 天，可选 1 小时 / 1 天 / 30 天
         *     - 密码可选（4–24 字符），查看次数可选（1–10000）
         *     - 每用户有效分享数受全局限额约束，超限返回 409
         */
        post: operations["create_share_api_v1_clipboard_items__id__shares_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clipboard/shares": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 我的分享
         * @description 分页查询当前用户的分享。支持 `status` 与 `item_id` 筛选；删除原记录前可用 `item_id` + `status=active` 统计有效分享数。
         */
        get: operations["list_shares_api_v1_clipboard_shares_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clipboard/shares/{id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * 撤销分享
         * @description 撤销后链接立即失效；重复撤销幂等。只能撤销本人的分享。
         */
        delete: operations["revoke_share_api_v1_clipboard_shares__id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/clipboard/shares/{id}/access-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 我的分享访问记录
         * @description 分页查询某条分享的成功访问记录，按访问时间倒序。**失败记录只有管理员能查看**。IP 已脱敏。
         */
        get: operations["list_access_logs_api_v1_clipboard_shares__id__access_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/public/shares/{token}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 公开分享元信息
         * @description 不返回正文、不计数。有密码时 `title` 为 null。
         */
        get: operations["public_meta_api_v1_public_shares__token__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/public/shares/{token}/access": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 查看分享正文
         * @description **唯一计数入口**：只有用户主动查看或提交正确密码时才调用。
         *
         *     页面加载、刷新、元信息查询均不计数。失败尝试会写入访问记录，但只有管理员能查看失败记录。
         */
        post: operations["public_access_api_v1_public_shares__token__access_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 后台概览统计 */
        get: operations["get_stats_api_v1_admin_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 用户分页列表 */
        get: operations["list_users_api_v1_admin_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 用户详情 */
        get: operations["get_user_api_v1_admin_users__user_id__get"];
        put?: never;
        post?: never;
        /** 删除用户（级联删除剪贴板） */
        delete: operations["delete_user_api_v1_admin_users__user_id__delete"];
        options?: never;
        head?: never;
        /** 修改用户资料 / 状态 / 角色 */
        patch: operations["update_user_api_v1_admin_users__user_id__patch"];
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/reset-password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 重置用户密码
         * @description 重置后该用户的全部旧令牌与 WebSocket 连接立即失效。新密码至少 8 个字符、同时包含字母和数字、不能包含目标用户名。
         */
        post: operations["reset_password_api_v1_admin_users__user_id__reset_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/clipboards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** 清空指定用户的剪贴板 */
        delete: operations["clear_user_clipboards_api_v1_admin_users__user_id__clipboards_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/shares": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 指定用户的分享记录
         * @description 分页查看某位用户的分享记录（不返回 token / 链接）。分享撤销等管理操作不在本期范围。
         */
        get: operations["list_user_shares_api_v1_admin_users__user_id__shares_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/shares": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 全局分享分页列表
         * @description 管理员查看全站分享；支持按状态与分享者用户名筛选。不返回 token / 链接；分享撤销等管理操作不在本期范围。
         */
        get: operations["list_all_shares_api_v1_admin_shares_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/clipboards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 全局剪贴板分页列表 */
        get: operations["list_clipboards_api_v1_admin_clipboards_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/clipboards/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 剪贴板详情（含完整正文） */
        get: operations["get_clipboard_api_v1_admin_clipboards__item_id__get"];
        put?: never;
        post?: never;
        /** 删除任意用户的单条剪贴板 */
        delete: operations["delete_clipboard_api_v1_admin_clipboards__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/audit-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 管理员操作审计列表 */
        get: operations["list_audit_logs_api_v1_admin_audit_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/invite-codes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 邀请码分页列表 */
        get: operations["list_invite_codes_api_v1_admin_invite_codes_get"];
        put?: never;
        /**
         * 生成邀请码
         * @description `max_uses` 必填，表示最大使用次数，用尽后邀请码自动失效。
         *
         *     **明文只在本次响应中返回一次**，数据库只保存 SHA-256 哈希。
         */
        post: operations["create_invite_code_api_v1_admin_invite_codes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/invite-codes/{code_id}/revoke": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 撤销邀请码 */
        post: operations["revoke_invite_code_api_v1_admin_invite_codes__code_id__revoke_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/invite-codes/{code_id}/usages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 邀请码使用详情
         * @description 列出通过该邀请码注册的用户，按注册时间倒序。
         */
        get: operations["list_invite_code_usages_api_v1_admin_invite_codes__code_id__usages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/settings/shares": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 读取分享限额设置
         * @description 返回每用户有效分享上限与最近更新人。普通用户返回 403。
         */
        get: operations["get_share_settings_api_v1_admin_settings_shares_get"];
        /**
         * 更新分享限额设置
         * @description 更新后立即生效：新创建分享按新限额校验，已有分享不会因调低限额被删除。
         *
         *     更新与审计 `settings.share_quota.update` 同事务提交，审计失败整体回滚。
         */
        put: operations["update_share_settings_api_v1_admin_settings_shares_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/share-access-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分享访问记录（成功 + 失败）
         * @description 管理员专用。失败记录只有本接口可见；用户端「我的分享」只返回成功记录。
         *
         *     支持按结果、分享、分享者用户名与时间范围筛选，按访问时间倒序。
         */
        get: operations["list_share_access_logs_api_v1_admin_share_access_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dev/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 重置为种子数据（⚠️ 会删除数据）
         * @description 删除演示用户的全部剪贴板项，并重新写入 4 条种子数据。
         *
         *     **仅用于本地开发与自动化测试收尾**：
         *     - 生产环境必须保持 `ENABLE_DEV_ROUTES=false`（此时本路由不注册，返回 404）
         *     - 只应指向开发库或测试库，绝不要指向生产库
         */
        post: operations["reset_store_api_v1_dev_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dev/db": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 数据库连通性探测
         * @description 返回当前连接的数据库名与 PostgreSQL 版本，用于确认后端连的是哪个库。
         */
        get: operations["db_info_api_v1_dev_db_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 服务信息
         * @description 返回服务基本信息与关键入口，便于健康检查。
         */
        get: operations["root__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 健康检查
         * @description 存活探针。
         */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AdminAuditLogList
         * @description 审计记录分页列表。
         */
        AdminAuditLogList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminAuditLogResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminAuditLogResponse
         * @description 一条管理员审计记录。
         */
        AdminAuditLogResponse: {
            /** Id */
            id: string;
            /** Admin Id */
            admin_id: string | null;
            /** Admin Username */
            admin_username: string;
            /** Action */
            action: string;
            /** Target Type */
            target_type: string | null;
            /** Target Id */
            target_id: string | null;
            /** Detail */
            detail: {
                [key: string]: unknown;
            } | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * AdminClipboardItemList
         * @description 剪贴板分页列表。
         */
        AdminClipboardItemList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminClipboardItemResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminClipboardItemResponse
         * @description 管理端剪贴板项（含所属用户名）。**不包含 `content_hash`**。
         */
        AdminClipboardItemResponse: {
            /** Id */
            id: string;
            /** User Id */
            user_id: string;
            /** Username */
            username: string;
            /** Title */
            title: string;
            content_type: components["schemas"]["ContentType"];
            /** Content */
            content: string;
            /** Preview */
            preview: string | null;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            } | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * AdminClipboardSortBy
         * @description 剪贴板列表排序字段。
         * @enum {string}
         */
        AdminClipboardSortBy: "created_at" | "updated_at";
        /**
         * AdminInviteCodeCreate
         * @description 创建邀请码请求。
         */
        AdminInviteCodeCreate: {
            /**
             * Label
             * @description 备注，便于辨认
             */
            label?: string | null;
            /**
             * Max Uses
             * @description 最大使用次数（必填），用尽后邀请码失效
             */
            max_uses: number;
            /**
             * Expires Days
             * @description 有效期天数，0 表示不过期
             * @default 7
             */
            expires_days: number;
        };
        /**
         * AdminInviteCodeCreated
         * @description 创建成功的响应：额外返回一次性明文。
         */
        AdminInviteCodeCreated: {
            /** Id */
            id: string;
            /**
             * Code Hint
             * @description 明文前 8 位，仅用于辨认
             */
            code_hint: string;
            /** Label */
            label: string | null;
            /**
             * Max Uses
             * @description 最大使用次数；历史数据可能为不限次数
             */
            max_uses?: number | null;
            /** Used Count */
            used_count: number;
            /**
             * Status
             * @description active / exhausted / expired / revoked
             */
            status: string;
            /** Expires At */
            expires_at: string | null;
            /** Revoked At */
            revoked_at: string | null;
            /** Last Used At */
            last_used_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Code
             * @description 邀请码明文，仅本次返回
             */
            code: string;
        };
        /**
         * AdminInviteCodeList
         * @description 邀请码分页列表。
         */
        AdminInviteCodeList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminInviteCodeResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminInviteCodeResponse
         * @description 邀请码表示。**明文只在创建时返回一次**，列表只展示 `code_hint`。
         */
        AdminInviteCodeResponse: {
            /** Id */
            id: string;
            /**
             * Code Hint
             * @description 明文前 8 位，仅用于辨认
             */
            code_hint: string;
            /** Label */
            label: string | null;
            /**
             * Max Uses
             * @description 最大使用次数；历史数据可能为不限次数
             */
            max_uses?: number | null;
            /** Used Count */
            used_count: number;
            /**
             * Status
             * @description active / exhausted / expired / revoked
             */
            status: string;
            /** Expires At */
            expires_at: string | null;
            /** Revoked At */
            revoked_at: string | null;
            /** Last Used At */
            last_used_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /**
         * AdminInviteCodeStatus
         * @description 邀请码状态筛选。
         * @enum {string}
         */
        AdminInviteCodeStatus: "all" | "active" | "exhausted" | "expired" | "revoked";
        /**
         * AdminInviteCodeUsage
         * @description 邀请码使用详情：通过该码注册的用户。
         */
        AdminInviteCodeUsage: {
            /** User Id */
            user_id: string;
            /** Username */
            username: string;
            /** Email */
            email: string;
            /**
             * Registered At
             * Format: date-time
             */
            registered_at: string;
        };
        /**
         * AdminInviteCodeUsageList
         * @description 邀请码使用详情分页列表。
         */
        AdminInviteCodeUsageList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminInviteCodeUsage"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminPasswordResetRequest
         * @description 重置密码请求。
         */
        AdminPasswordResetRequest: {
            /**
             * Password
             * @description 新密码，至少 8 个字符，必须同时包含字母和数字，不能包含目标用户名，且不超过 72 字节（bcrypt 上限）
             */
            password: string;
        };
        /**
         * AdminShareAccessLogList
         * @description 管理端访问记录分页列表。
         */
        AdminShareAccessLogList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminShareAccessLogResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminShareAccessLogResponse
         * @description 管理端访问记录（含原始 IP；仅内网 / VPN 可访问）。
         */
        AdminShareAccessLogResponse: {
            /** Id */
            id: string;
            /** Share Id */
            share_id: string;
            /** Share Title */
            share_title: string;
            /** Owner Id */
            owner_id: string;
            /** Owner Username */
            owner_username: string;
            /**
             * Accessed At
             * Format: date-time
             */
            accessed_at: string;
            /**
             * Result
             * @description success / password_failed / expired / revoked / exhausted / owner_disabled
             */
            result: string;
            /** Ip */
            ip?: string | null;
            /** User Agent */
            user_agent?: string | null;
        };
        /**
         * AdminShareAccessResultFilter
         * @description 管理端访问记录的结果筛选。
         * @enum {string}
         */
        AdminShareAccessResultFilter: "all" | "success" | "failure";
        /**
         * AdminShareList
         * @description 全局分享分页列表。
         */
        AdminShareList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminShareResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminShareResponse
         * @description 管理端全局分享列表项（不返回 token / 链接）。
         */
        AdminShareResponse: {
            /** Id */
            id: string;
            /** Item Id */
            item_id: string;
            /** Title */
            title: string;
            /** Owner Id */
            owner_id: string;
            /** Owner Username */
            owner_username: string;
            mode: components["schemas"]["ShareMode"];
            status: components["schemas"]["ShareStatus"];
            /** Password Protected */
            password_protected: boolean;
            /** View Count */
            view_count: number;
            /** Max Views */
            max_views?: number | null;
            /** Remaining Views */
            remaining_views?: number | null;
            /** Expires At */
            expires_at?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Revoked At */
            revoked_at?: string | null;
        };
        /**
         * AdminStatsResponse
         * @description 后台概览统计。
         */
        AdminStatsResponse: {
            /** User Count */
            user_count: number;
            /** Active User Count */
            active_user_count: number;
            /** Admin Count */
            admin_count: number;
            /** Item Count */
            item_count: number;
            /** Total Bytes */
            total_bytes: number;
            /** New Users 7D */
            new_users_7d: number;
            /** New Items 7D */
            new_items_7d: number;
            /**
             * Invite Code Count
             * @description 邀请码总数
             */
            invite_code_count: number;
            /**
             * Active Invite Count
             * @description 当前可用的邀请码数
             */
            active_invite_count: number;
            /**
             * Invite Used Count
             * @description 邀请码累计使用次数
             */
            invite_used_count: number;
            /**
             * Share Count
             * @description 分享总数
             */
            share_count: number;
            /**
             * Active Share Count
             * @description 当前有效分享数
             */
            active_share_count: number;
        };
        /**
         * AdminUserList
         * @description 用户分页列表。
         */
        AdminUserList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminUserResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminUserResponse
         * @description 管理端用户表示（含统计字段）。
         */
        AdminUserResponse: {
            /**
             * Id
             * @description 用户 UUID
             */
            id: string;
            /**
             * Username
             * @description 用户名
             */
            username: string;
            /**
             * Email
             * @description 邮箱
             */
            email: string;
            /**
             * Nickname
             * @description 昵称
             */
            nickname?: string | null;
            /**
             * Is Admin
             * @description 是否管理员
             */
            is_admin: boolean;
            /**
             * Is Active
             * @description 账号是否启用
             */
            is_active: boolean;
            /**
             * Created At
             * Format: date-time
             * @description 注册时间（ISO 8601 UTC）
             */
            created_at: string;
            /**
             * Last Login At
             * @description 最后登录时间
             */
            last_login_at?: string | null;
            /**
             * Item Count
             * @description 剪贴板条数
             * @default 0
             */
            item_count: number;
            /**
             * Last Item At
             * @description 最后一条剪贴板更新时间
             */
            last_item_at?: string | null;
            /**
             * Share Limit
             * @description 单独设置的分享上限；null 表示跟随全局默认值
             */
            share_limit?: number | null;
        };
        /**
         * AdminUserRole
         * @description 用户列表的角色筛选。
         * @enum {string}
         */
        AdminUserRole: "all" | "admin" | "user";
        /**
         * AdminUserShareList
         * @description 用户分享记录分页列表。
         */
        AdminUserShareList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["AdminUserShareResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * AdminUserShareResponse
         * @description 管理端查看某位用户的分享记录（不返回 token / 链接）。
         */
        AdminUserShareResponse: {
            /** Id */
            id: string;
            /** Item Id */
            item_id: string;
            mode: components["schemas"]["ShareMode"];
            status: components["schemas"]["ShareStatus"];
            /** Title */
            title: string;
            /** Password Protected */
            password_protected: boolean;
            /** Expires At */
            expires_at?: string | null;
            /** Max Views */
            max_views?: number | null;
            /** View Count */
            view_count: number;
            /** Remaining Views */
            remaining_views?: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Revoked At */
            revoked_at?: string | null;
        };
        /**
         * AdminUserSortBy
         * @description 用户列表排序字段。
         * @enum {string}
         */
        AdminUserSortBy: "created_at" | "last_login_at" | "item_count";
        /**
         * AdminUserStatus
         * @description 用户列表的状态筛选。
         * @enum {string}
         */
        AdminUserStatus: "all" | "active" | "disabled";
        /**
         * AdminUserUpdate
         * @description 修改用户资料/状态/角色；所有字段可选，只更新显式传入的字段。
         */
        AdminUserUpdate: {
            /** Nickname */
            nickname?: string | null;
            /** Email */
            email?: string | null;
            /**
             * Is Active
             * @description false = 禁用账号
             */
            is_active?: boolean | null;
            /**
             * Is Admin
             * @description false = 取消管理员
             */
            is_admin?: boolean | null;
            /**
             * Share Limit
             * @description 单独设置的分享上限，范围 1–10000；显式传 null 表示清除并跟随全局
             */
            share_limit?: number | null;
        };
        /**
         * AuthResponse
         * @description 注册/登录响应：用户信息 + 令牌（供前端一次拿到完整上下文）。
         */
        AuthResponse: {
            /**
             * Id
             * @description 用户 UUID
             */
            id: string;
            /**
             * Username
             * @description 用户名
             */
            username: string;
            /**
             * Email
             * @description 邮箱
             */
            email: string;
            /**
             * Nickname
             * @description 昵称
             */
            nickname?: string | null;
            /**
             * Avatar Url
             * @description 头像地址
             */
            avatar_url?: string | null;
            /**
             * Is Admin
             * @description 是否管理员（仅用于展示，权限仍由服务端校验）
             * @default false
             */
            is_admin: boolean;
            /**
             * Created At
             * Format: date-time
             * @description 注册时间（ISO 8601 UTC）
             */
            created_at: string;
            /** @description 令牌信息，便于前端一次取用 */
            token: components["schemas"]["TokenResponse"];
        };
        /**
         * ClipboardDeleteResponse
         * @description 删除单条剪贴板项的响应。
         */
        ClipboardDeleteResponse: {
            /**
             * Success
             * @description 操作是否成功
             * @default true
             */
            success: boolean;
            /**
             * Message
             * @description 人类可读的结果说明
             */
            message: string;
            /**
             * Id
             * @description 被删除的剪贴板项 UUID
             */
            id: string;
        };
        /**
         * ClipboardItemCreate
         * @description 创建剪贴板项请求。
         */
        ClipboardItemCreate: {
            /**
             * Content
             * @description 剪贴板内容（阶段一为纯文本）
             */
            content: string;
            /**
             * Title
             * @description 标题。留空时由服务端自动生成，格式 `剪贴板 · <月-日 时:分>`，时间按 `timezone` 指定的时区展示，例如 `剪贴板 · 10-05 21:56`
             */
            title?: string | null;
            /**
             * Timezone
             * @description 自动生成标题时使用的 IANA 时区，例如 `Asia/Shanghai`。**只影响标题里展示的时间，数据库仍统一存 UTC**。留空时用服务端 `DEFAULT_TIMEZONE` 配置
             */
            timezone?: string | null;
            /**
             * @description 内容类型，阶段一固定 text
             * @default text
             */
            content_type: components["schemas"]["ContentType"];
            /**
             * Preview
             * @description 预览文本；不传时由服务端截取正文生成
             */
            preview?: string | null;
            /**
             * Metadata
             * @description 附加元信息，例如 {"mime": "text/plain", "size": 1024}
             */
            metadata?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * ClipboardItemList
         * @description 剪贴板列表响应（携带分页元信息）。
         */
        ClipboardItemList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["ClipboardItemResponse"][];
            /**
             * Page
             * @description 当前页码，从 1 开始
             */
            page: number;
            /**
             * Size
             * @description 每页条数
             */
            size: number;
            /**
             * Total
             * @description 符合条件的总条数
             */
            total: number;
            /**
             * Pages
             * @description 总页数
             */
            pages: number;
        };
        /**
         * ClipboardItemResponse
         * @description 剪贴板项对外表示。
         *
         *     注意：`content_hash` 不对外暴露，仅服务端用于去重。
         */
        ClipboardItemResponse: {
            /**
             * Id
             * @description 剪贴板项 UUID
             */
            id: string;
            /**
             * User Id
             * @description 所属用户 UUID
             */
            user_id: string;
            /**
             * Title
             * @description 标题，用户未填写时由服务端自动生成
             */
            title: string;
            /** @description 内容类型 */
            content_type: components["schemas"]["ContentType"];
            /**
             * Content
             * @description 文字内容或文件 URL
             */
            content: string;
            /**
             * Preview
             * @description 预览文本
             */
            preview?: string | null;
            /**
             * Metadata
             * @description 附加元信息
             */
            metadata?: {
                [key: string]: unknown;
            } | null;
            /**
             * Created At
             * Format: date-time
             * @description 创建时间（ISO 8601 UTC）
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             * @description 最后更新时间（ISO 8601 UTC）
             */
            updated_at: string;
        };
        /**
         * ClipboardItemUpdate
         * @description 更新剪贴板项请求（用于自动保存复用同一条草稿记录）。
         *
         *     所有字段可选，只更新显式传入的字段。
         */
        ClipboardItemUpdate: {
            /** Content */
            content?: string | null;
            /** Title */
            title?: string | null;
            /**
             * Timezone
             * @description 内容变化且未显式传 `title` 时，重新生成标题所用的 IANA 时区
             */
            timezone?: string | null;
            /** Preview */
            preview?: string | null;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * ClipboardShareCreate
         * @description 创建分享请求。
         */
        ClipboardShareCreate: {
            /**
             * @description snapshot 快照 / live 跟随最新
             * @default snapshot
             */
            mode: components["schemas"]["ShareMode"];
            /**
             * @description 有效期：1h / 1d / 7d / 30d，默认 7d
             * @default 7d
             */
            expires_in: components["schemas"]["ShareExpiresIn"];
            /**
             * Password
             * @description 访问密码，可空；4–24 字符，UTF-8 不超过 72 字节
             */
            password?: string | null;
            /**
             * Max Views
             * @description 最大查看次数，可空（不限）
             */
            max_views?: number | null;
        };
        /**
         * ClipboardShareList
         * @description 我的分享分页列表。
         */
        ClipboardShareList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["ClipboardShareResponse"][];
            /**
             * Page
             * @description 当前页码，从 1 开始
             */
            page: number;
            /**
             * Size
             * @description 每页条数
             */
            size: number;
            /**
             * Total
             * @description 符合条件的总条数
             */
            total: number;
            /**
             * Pages
             * @description 总页数
             */
            pages: number;
        };
        /**
         * ClipboardShareResponse
         * @description 登录态下的分享表示（含 token 与完整链接）。
         */
        ClipboardShareResponse: {
            /**
             * Id
             * @description 分享 UUID
             */
            id: string;
            /**
             * Item Id
             * @description 原剪贴板项 UUID
             */
            item_id: string;
            /** @description 内容模式 */
            mode: components["schemas"]["ShareMode"];
            /** @description 当前状态 */
            status: components["schemas"]["ShareStatus"];
            /**
             * Title
             * @description 创建时的标题
             */
            title: string;
            /**
             * Token
             * @description 分享 token
             */
            token: string;
            /**
             * Url
             * @description 完整公开链接
             */
            url: string;
            /**
             * Password Protected
             * @description 是否设置访问密码
             */
            password_protected: boolean;
            /**
             * Expires At
             * @description 到期时间（ISO 8601 UTC）
             */
            expires_at?: string | null;
            /**
             * Max Views
             * @description 最大查看次数；空表示不限
             */
            max_views?: number | null;
            /**
             * View Count
             * @description 已成功查看次数
             */
            view_count: number;
            /**
             * Remaining Views
             * @description 剩余查看次数；空表示不限
             */
            remaining_views?: number | null;
            /**
             * Created At
             * Format: date-time
             * @description 创建时间（ISO 8601 UTC）
             */
            created_at: string;
            /**
             * Last Viewed At
             * @description 最后一次成功查看时间
             */
            last_viewed_at?: string | null;
        };
        /**
         * ContentType
         * @description 剪贴板内容类型。阶段一仅实现 `text`。
         * @enum {string}
         */
        ContentType: "text" | "image" | "file";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * MessageResponse
         * @description 通用消息响应（删除类接口）。
         */
        MessageResponse: {
            /**
             * Success
             * @description 操作是否成功
             * @default true
             */
            success: boolean;
            /**
             * Message
             * @description 人类可读的结果说明
             */
            message: string;
        };
        /**
         * PublicShareAccessRequest
         * @description 公开查看正文请求；无密码分享可传空对象。
         */
        PublicShareAccessRequest: {
            /**
             * Password
             * @description 访问密码
             */
            password?: string | null;
        };
        /**
         * PublicShareContent
         * @description 公开查看正文响应。
         */
        PublicShareContent: {
            /**
             * Title
             * @description 标题
             */
            title: string;
            /**
             * Content
             * @description 文字正文
             */
            content: string;
            /** @description 内容类型 */
            content_type: components["schemas"]["ContentType"];
            /**
             * Created At
             * Format: date-time
             * @description 原记录创建时间（ISO 8601 UTC）
             */
            created_at: string;
            /**
             * Expires At
             * @description 分享到期时间
             */
            expires_at?: string | null;
            /**
             * Remaining Views
             * @description 本次查看后的剩余次数；空表示不限
             */
            remaining_views?: number | null;
        };
        /**
         * PublicShareMeta
         * @description 公开分享元信息；不返回正文、不计数。
         */
        PublicShareMeta: {
            /**
             * Title
             * @description 有密码时为 null，避免未解锁泄露标题
             */
            title?: string | null;
            /** @description 内容模式 */
            mode: components["schemas"]["ShareMode"];
            /** @description 内容类型 */
            content_type: components["schemas"]["ContentType"];
            /**
             * Password Required
             * @description 是否需要访问密码
             */
            password_required: boolean;
            /**
             * Expires At
             * @description 到期时间
             */
            expires_at?: string | null;
            /**
             * Remaining Views
             * @description 剩余查看次数；空表示不限
             */
            remaining_views?: number | null;
        };
        /**
         * ShareAccessLogList
         * @description 访问记录分页列表。
         */
        ShareAccessLogList: {
            /**
             * Items
             * @description 当前页数据
             */
            items: components["schemas"]["ShareAccessLogResponse"][];
            /** Page */
            page: number;
            /** Size */
            size: number;
            /** Total */
            total: number;
            /** Pages */
            pages: number;
        };
        /**
         * ShareAccessLogResponse
         * @description 所有者可见的访问记录（只含成功记录，IP 已脱敏）。
         */
        ShareAccessLogResponse: {
            /** Id */
            id: string;
            /**
             * Accessed At
             * Format: date-time
             */
            accessed_at: string;
            result: components["schemas"]["ShareAccessResult"];
            /**
             * Ip Masked
             * @description 脱敏 IP
             */
            ip_masked?: string | null;
            /**
             * User Agent
             * @description User-Agent，最多 200 字符
             */
            user_agent?: string | null;
        };
        /**
         * ShareAccessResult
         * @description 访问记录结果。失败结果仅管理员可见。
         * @enum {string}
         */
        ShareAccessResult: "success" | "password_failed" | "expired" | "revoked" | "exhausted" | "owner_disabled";
        /**
         * ShareExpiresIn
         * @description 分享有效期选项；P0 不支持永久。
         * @enum {string}
         */
        ShareExpiresIn: "1h" | "1d" | "7d" | "30d";
        /**
         * ShareMode
         * @description 分享内容模式。
         * @enum {string}
         */
        ShareMode: "snapshot" | "live";
        /**
         * ShareSettingsResponse
         * @description 管理端分享限额设置。
         */
        ShareSettingsResponse: {
            /**
             * User Share Limit
             * @description 每用户有效分享上限
             */
            user_share_limit: number;
            /**
             * Updated At
             * @description 最近更新时间
             */
            updated_at?: string | null;
            /**
             * Updated By
             * @description 最近更新人 UUID
             */
            updated_by?: string | null;
            /**
             * Updated By Username
             * @description 最近更新人用户名
             */
            updated_by_username?: string | null;
        };
        /**
         * ShareSettingsUpdate
         * @description 更新分享限额请求。
         */
        ShareSettingsUpdate: {
            /**
             * User Share Limit
             * @description 每用户有效分享上限，范围 1–10000
             */
            user_share_limit: number;
        };
        /**
         * ShareStatus
         * @description 分享展示状态。判定顺序：撤销 → 过期 → 次数用尽 → 有效。
         * @enum {string}
         */
        ShareStatus: "active" | "expired" | "exhausted" | "revoked";
        /**
         * SortBy
         * @description 列表排序字段。
         * @enum {string}
         */
        SortBy: "created_at" | "updated_at";
        /**
         * SortOrder
         * @description 排序方向。
         * @enum {string}
         */
        SortOrder: "desc" | "asc";
        /**
         * TokenResponse
         * @description 登录/注册成功后返回的令牌。
         */
        TokenResponse: {
            /**
             * Access Token
             * @description JWT 访问令牌
             */
            access_token: string;
            /**
             * Token Type
             * @description 令牌类型，固定 bearer
             * @default bearer
             */
            token_type: string;
            /**
             * Expires In
             * @description 有效期（秒）
             */
            expires_in: number;
            /** @description 当前登录用户 */
            user: components["schemas"]["UserResponse"];
        };
        /**
         * UserLoginRequest
         * @description 登录请求。
         */
        UserLoginRequest: {
            /**
             * Username
             * @description 用户名或邮箱
             */
            username: string;
            /**
             * Password
             * @description 密码
             */
            password: string;
        };
        /**
         * UserPasswordChangeRequest
         * @description 修改密码请求。新密码的复杂度由 Schema 校验，用户名包含检查在路由层完成。
         */
        UserPasswordChangeRequest: {
            /**
             * Old Password
             * @description 当前密码
             */
            old_password: string;
            /**
             * New Password
             * @description 新密码，至少 8 个字符，必须同时包含字母和数字，不能包含用户名，且不超过 72 字节（bcrypt 上限）
             */
            new_password: string;
        };
        /**
         * UserRegisterRequest
         * @description 注册请求。
         */
        UserRegisterRequest: {
            /**
             * Username
             * @description 用户名，3-32 字符
             */
            username: string;
            /**
             * Email
             * @description 邮箱
             */
            email: string;
            /**
             * Password
             * @description 密码，至少 8 个字符，必须同时包含字母和数字，不能包含用户名，且不超过 72 字节（bcrypt 上限）
             */
            password: string;
            /**
             * Invite Code
             * @description 邀请码。服务端设置 `REGISTRATION_INVITE_CODE` 时必填且必须匹配，否则返回 403；未设置时可为空
             */
            invite_code?: string | null;
        };
        /**
         * UserResponse
         * @description 用户公开信息。**绝不包含密码哈希**。
         */
        UserResponse: {
            /**
             * Id
             * @description 用户 UUID
             */
            id: string;
            /**
             * Username
             * @description 用户名
             */
            username: string;
            /**
             * Email
             * @description 邮箱
             */
            email: string;
            /**
             * Nickname
             * @description 昵称
             */
            nickname?: string | null;
            /**
             * Avatar Url
             * @description 头像地址
             */
            avatar_url?: string | null;
            /**
             * Is Admin
             * @description 是否管理员（仅用于展示，权限仍由服务端校验）
             * @default false
             */
            is_admin: boolean;
            /**
             * Created At
             * Format: date-time
             * @description 注册时间（ISO 8601 UTC）
             */
            created_at: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    register_api_v1_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserRegisterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthResponse"];
                };
            };
            /** @description 邀请码无效（服务端已开启注册验证） */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 用户名或邮箱已被占用 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserLoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthResponse"];
                };
            };
            /** @description 用户名或密码错误 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 账号已被禁用 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_password_api_v1_auth_change_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPasswordChangeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description 当前密码错误，或新密码不满足策略 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 未提供令牌，或令牌无效/已过期 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserResponse"];
                };
            };
            /** @description 未提供令牌，或令牌无效/已过期 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_items_api_v1_clipboard_items_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 按内容类型筛选 */
                content_type?: components["schemas"]["ContentType"] | null;
                /** @description 按标题或内容关键字搜索 */
                search?: string | null;
                /** @description 排序字段 */
                sort_by?: components["schemas"]["SortBy"];
                /** @description 排序方向 */
                order?: components["schemas"]["SortOrder"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardItemList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_item_api_v1_clipboard_items_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClipboardItemCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardItemResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clear_items_api_v1_clipboard_items_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
        };
    };
    get_item_api_v1_clipboard_items__id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardItemResponse"];
                };
            };
            /** @description 剪贴板项不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_item_api_v1_clipboard_items__id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardDeleteResponse"];
                };
            };
            /** @description 剪贴板项不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_item_api_v1_clipboard_items__id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClipboardItemUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardItemResponse"];
                };
            };
            /** @description 剪贴板项不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 改后的内容与该用户的另一条记录重复 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_share_api_v1_clipboard_items__id__shares_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClipboardShareCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardShareResponse"];
                };
            };
            /** @description 阶段一仅支持文字分享 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 剪贴板项不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 有效分享数达到上限 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_shares_api_v1_clipboard_shares_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 按状态筛选 */
                status?: components["schemas"]["ShareStatus"] | null;
                /** @description 按原剪贴板项 UUID 筛选 */
                item_id?: string | null;
                /** @description 按分享标题或内容关键字搜索 */
                search?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardShareList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_share_api_v1_clipboard_shares__id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description 分享不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_access_logs_api_v1_clipboard_shares__id__access_logs_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
            };
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareAccessLogList"];
                };
            };
            /** @description 分享不存在或不属于当前用户 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    public_meta_api_v1_public_shares__token__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicShareMeta"];
                };
            };
            /** @description 分享不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 分享已失效 */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 请求过于频繁 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    public_access_api_v1_public_shares__token__access_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicShareAccessRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PublicShareContent"];
                };
            };
            /** @description 密码错误或未提供 */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 分享不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 分享已失效 */
            410: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description 尝试过于频繁 */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    get_stats_api_v1_admin_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminStatsResponse"];
                };
            };
        };
    };
    list_users_api_v1_admin_users_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 匹配用户名或邮箱 */
                search?: string | null;
                /** @description 账号状态筛选 */
                status?: components["schemas"]["AdminUserStatus"];
                /** @description 角色筛选 */
                role?: components["schemas"]["AdminUserRole"];
                /** @description 排序字段 */
                sort_by?: components["schemas"]["AdminUserSortBy"];
                /** @description 排序方向 */
                order?: components["schemas"]["SortOrder"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_user_api_v1_admin_users__user_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserResponse"];
                };
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_user_api_v1_admin_users__user_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description 不能删除当前管理员自己 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_user_api_v1_admin_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminUserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserResponse"];
                };
            };
            /** @description 试图禁用或降权当前管理员自己 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 邮箱已被占用 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_password_api_v1_admin_users__user_id__reset_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminPasswordResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clear_user_clipboards_api_v1_admin_users__user_id__clipboards_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_user_shares_api_v1_admin_users__user_id__shares_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，最大 100 */
                size?: number;
                /** @description 按状态筛选 */
                status?: components["schemas"]["ShareStatus"] | null;
            };
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminUserShareList"];
                };
            };
            /** @description 用户不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_shares_api_v1_admin_shares_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，最大 100 */
                size?: number;
                /** @description 按分享状态筛选 */
                status?: components["schemas"]["ShareStatus"] | null;
                /** @description 按分享者用户名模糊筛选 */
                username?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminShareList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_clipboards_api_v1_admin_clipboards_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 按用户 UUID 精确筛选 */
                user_id?: string | null;
                /** @description 按用户名模糊筛选 */
                username?: string | null;
                /** @description 匹配标题或内容 */
                search?: string | null;
                /** @description 按内容类型筛选 */
                content_type?: components["schemas"]["ContentType"] | null;
                /** @description 排序字段 */
                sort_by?: components["schemas"]["AdminClipboardSortBy"];
                /** @description 排序方向 */
                order?: components["schemas"]["SortOrder"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminClipboardItemList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_clipboard_api_v1_admin_clipboards__item_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminClipboardItemResponse"];
                };
            };
            /** @description 剪贴板项不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_clipboard_api_v1_admin_clipboards__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClipboardDeleteResponse"];
                };
            };
            /** @description 剪贴板项不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audit_logs_api_v1_admin_audit_logs_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 按管理员用户名模糊筛选 */
                admin_username?: string | null;
                /** @description 按动作精确筛选 */
                action?: string | null;
                /** @description 按目标对象 UUID 筛选 */
                target_id?: string | null;
                /** @description 起始时间（ISO 8601） */
                start?: string | null;
                /** @description 结束时间（ISO 8601） */
                end?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminAuditLogList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_invite_codes_api_v1_admin_invite_codes_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 按状态筛选 */
                status?: components["schemas"]["AdminInviteCodeStatus"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminInviteCodeList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_invite_code_api_v1_admin_invite_codes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdminInviteCodeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminInviteCodeCreated"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_invite_code_api_v1_admin_invite_codes__code_id__revoke_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                code_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminInviteCodeResponse"];
                };
            };
            /** @description 邀请码不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_invite_code_usages_api_v1_admin_invite_codes__code_id__usages_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
            };
            header?: never;
            path: {
                code_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminInviteCodeUsageList"];
                };
            };
            /** @description 邀请码不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_share_settings_api_v1_admin_settings_shares_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareSettingsResponse"];
                };
            };
        };
    };
    update_share_settings_api_v1_admin_settings_shares_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ShareSettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ShareSettingsResponse"];
                };
            };
            /** @description 限额超出 1–10000 范围 */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_share_access_logs_api_v1_admin_share_access_logs_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 10，最大 100 */
                size?: number;
                /** @description 结果筛选 */
                result?: components["schemas"]["AdminShareAccessResultFilter"];
                /** @description 按分享 UUID 筛选 */
                share_id?: string | null;
                /** @description 按分享者用户名模糊筛选 */
                username?: string | null;
                /** @description 起始时间（ISO 8601） */
                start?: string | null;
                /** @description 结束时间（ISO 8601） */
                end?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdminShareAccessLogList"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_store_api_v1_dev_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageResponse"];
                };
            };
        };
    };
    db_info_api_v1_dev_db_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    root__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
}
