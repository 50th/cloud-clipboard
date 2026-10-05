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
         * 用户注册（假数据）
         * @description 第 1 步不落库、不校验唯一性，固定返回演示用户与假 token。
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
         * 用户登录（假数据）
         * @description 任意用户名密码均返回演示用户与假 token；第 4 步接入真实校验。
         */
        post: operations["login_api_v1_auth_login_post"];
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
         * @description 当前返回演示用户；第 4 步接入 JWT 后返回该 token 对应的用户。
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
         * @description 提交文字内容。`title` 留空时由服务端自动生成（`<用户名> · <月-日 时:分>`），时间按 `timezone`（IANA 时区名，前端会传浏览器时区）展示，例如 `demo · 10-05 21:56`。
         *
         *     **已内置内容去重**：同一用户提交相同 `content` 时不创建新记录，只更新 `updated_at`；此时仅当显式传了 `title` 才覆盖标题（第 6 步对应广播 `clipboard.updated`）。
         */
        post: operations["create_item_api_v1_clipboard_items_post"];
        /**
         * 清空剪贴板
         * @description 删除当前用户的全部剪贴板项（第 5 步对应广播 `clipboard.cleared`）。
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
             * @description 标题。留空时由服务端自动生成，格式 `<用户名> · <月-日 时:分>`，时间按 `timezone` 指定的时区展示，例如 `demo · 10-05 21:56`
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
             * @description 密码，6-72 字符（bcrypt 上限 72 字节）
             */
            password: string;
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
        requestBody?: never;
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
        };
    };
    list_items_api_v1_clipboard_items_get: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页条数，默认 20，最大 100 */
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
