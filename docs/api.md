# 云剪贴板 · API 契约

> **本文件由运行中的后端导出，是接口契约的存档副本。**
> 契约的事实来源始终是 `server/app/schemas/`（Pydantic Schema）。
> 在线交互式文档：<http://127.0.0.1:8000/docs> · 机器可读：<http://127.0.0.1:8000/openapi.json>

## 导出方式

```powershell
# 方式一：从运行中的后端拉取（推荐，永远与实现一致）
cd server
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
Invoke-RestMethod http://127.0.0.1:8000/openapi.json | ConvertTo-Json -Depth 30 | Set-Content docs\api.yaml -Encoding utf8

# 方式二：不启动服务直接导出（第 3 步接入数据库后需带 .env）
cd server
.\venv\Scripts\python.exe -c "import json,sys; from app.main import app; json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2)" > ..\docs\api.yaml
```

## 接口契约修改流程（AGENT.md 第 5 节）

1. 改 `server/app/schemas/`（**契约唯一事实来源**）
2. 重启 FastAPI，确认 `/openapi.json` 已更新
3. 重新生成本文件
4. 重新生成 Web 端类型：`cd web && pnpm run gen:api`
5. 同步鸿蒙端 `harmony/entry/src/main/ets/models/ClipboardItem.ets`（第 7 步创建后）

---

## 接口摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（当前返回演示用户 + 假 token） |
| POST | `/api/v1/auth/login` | 登录（当前返回演示用户 + 假 token） |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/clipboard/items` | 创建；`title` 留空时服务端自动生成 |
| GET | `/api/v1/clipboard/items` | 列表：分页 / 类型筛选 / 按标题或内容搜索 / 排序 |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | 重置种子数据（**仅开发路由开启时注册**） |
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |
| WS | `/api/v1/clipboard/ws?token=xxx` | 实时同步（第 5 步，协议见 `ws-protocol.md`） |

## 核心数据契约

### ClipboardItemResponse

```python
class ClipboardItemResponse(BaseModel):
    id: str                    # uuid
    user_id: str               # uuid
    title: str                 # 用户填写；留空时服务端生成 "demo · 10-03 12:55"
    content_type: ContentType  # text | image | file
    content: str               # 文字内容或文件 URL
    preview: Optional[str]     # 预览文本
    metadata: Optional[dict]   # {"mime": "text/plain", "size": 1024, ...}
    created_at: datetime       # ISO 8601 UTC
    updated_at: datetime       # ISO 8601 UTC
```

### 关键约定

- 时间统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`
- `content_hash` **不对外暴露**，仅服务端用于去重
- 去重：同一用户提交相同 `content` → 更新时间戳、不新建记录；**不覆盖已有标题**（除非本次显式传 `title`）
- 搜索同时匹配 `title` 与 `content`
- 分页：`page` 从 1 开始，`size` 默认 20、最大 100
- 阶段一仅支持 `content_type = text`；`image` / `file` 属阶段二、阶段三

---

## 当前 OpenAPI 文档（自动导出，请勿手工编辑）

<!-- 每次修改接口后重新执行上面的导出命令，覆盖以下代码块 -->

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Cloud Clipboard",
    "description": "跨平台云剪贴板服务 —— 多设备剪贴板内容实时同步。当前为阶段一（文字剪贴板 MVP）第 1 步：骨架 + 数据契约。",
    "version": "0.1.0"
  },
  "paths": {
    "/api/v1/auth/register": {
      "post": {
        "tags": [
          "认证"
        ],
        "summary": "用户注册（假数据）",
        "description": "第 1 步不落库、不校验唯一性，固定返回演示用户与假 token。",
        "operationId": "register_api_v1_auth_register_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserRegisterRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "201": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/AuthResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/login": {
      "post": {
        "tags": [
          "认证"
        ],
        "summary": "用户登录（假数据）",
        "description": "任意用户名密码均返回演示用户与假 token；第 4 步接入真实校验。",
        "operationId": "login_api_v1_auth_login_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserLoginRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/AuthResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/me": {
      "get": {
        "tags": [
          "认证"
        ],
        "summary": "获取当前用户",
        "description": "默认返回演示用户；通过 `Authorization` 头传入 token 后应返回该 token 对应用户。",
        "operationId": "me_api_v1_auth_me_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/UserResponse"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/clipboard/items": {
      "post": {
        "tags": [
          "剪贴板"
        ],
        "summary": "创建剪贴板项",
        "description": "提交文字内容。`title` 留空时由服务端自动生成（`<用户名> · <月-日 时:分>`）。\n\n**已内置内容去重**：同一用户提交相同 `content` 时不创建新记录，只更新 `updated_at`；此时仅当显式传了 `title` 才覆盖标题（第 6 步对应广播 `clipboard.updated`）。",
        "operationId": "create_item_api_v1_clipboard_items_post",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ClipboardItemCreate"
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ClipboardItemResponse"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "get": {
        "tags": [
          "剪贴板"
        ],
        "summary": "获取剪贴板列表",
        "description": "支持分页、按 `content_type` 筛选、按**标题或内容**关键字搜索与排序。",
        "operationId": "list_items_api_v1_clipboard_items_get",
        "parameters": [
          {
            "name": "page",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "minimum": 1,
              "description": "页码，从 1 开始",
              "default": 1,
              "title": "Page"
            },
            "description": "页码，从 1 开始"
          },
          {
            "name": "size",
            "in": "query",
            "required": false,
            "schema": {
              "type": "integer",
              "maximum": 100,
              "minimum": 1,
              "description": "每页条数，默认 20，最大 100",
              "default": 20,
              "title": "Size"
            },
            "description": "每页条数，默认 20，最大 100"
          },
          {
            "name": "content_type",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "$ref": "#/components/schemas/ContentType"
                },
                {
                  "type": "null"
                }
              ],
              "description": "按内容类型筛选",
              "title": "Content Type"
            },
            "description": "按内容类型筛选"
          },
          {
            "name": "search",
            "in": "query",
            "required": false,
            "schema": {
              "anyOf": [
                {
                  "type": "string",
                  "maxLength": 200
                },
                {
                  "type": "null"
                }
              ],
              "description": "按标题或内容关键字搜索",
              "title": "Search"
            },
            "description": "按标题或内容关键字搜索"
          },
          {
            "name": "sort_by",
            "in": "query",
            "required": false,
            "schema": {
              "$ref": "#/components/schemas/SortBy",
              "description": "排序字段",
              "default": "created_at"
            },
            "description": "排序字段"
          },
          {
            "name": "order",
            "in": "query",
            "required": false,
            "schema": {
              "$ref": "#/components/schemas/SortOrder",
              "description": "排序方向",
              "default": "desc"
            },
            "description": "排序方向"
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ClipboardItemList"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "delete": {
        "tags": [
          "剪贴板"
        ],
        "summary": "清空剪贴板",
        "description": "删除当前用户的全部剪贴板项（第 5 步对应广播 `clipboard.cleared`）。",
        "operationId": "clear_items_api_v1_clipboard_items_delete",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/MessageResponse"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/clipboard/items/{id}": {
      "get": {
        "tags": [
          "剪贴板"
        ],
        "summary": "获取剪贴板详情",
        "operationId": "get_item_api_v1_clipboard_items__id__get",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ClipboardItemResponse"
                }
              }
            }
          },
          "404": {
            "description": "剪贴板项不存在或不属于当前用户"
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      },
      "delete": {
        "tags": [
          "剪贴板"
        ],
        "summary": "删除单条剪贴板项",
        "operationId": "delete_item_api_v1_clipboard_items__id__delete",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/ClipboardDeleteResponse"
                }
              }
            }
          },
          "404": {
            "description": "剪贴板项不存在或不属于当前用户"
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/dev/reset": {
      "post": {
        "tags": [
          "系统"
        ],
        "summary": "重置数据为种子数据（仅开发环境）",
        "description": "清空当前数据并重新灌入 4 条种子数据，用于自动化测试收尾和反复手工验证。\n\n**⚠️ 第 3 步接入数据库后本接口会变成清库操作**，因此：\n- 生产环境必须保持 `ENABLE_DEV_ROUTES=false`（此时本路由不注册，返回 404）\n- 只应指向测试数据库使用",
        "operationId": "reset_store_api_v1_dev_reset_post",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/MessageResponse"
                }
              }
            }
          }
        }
      }
    },
    "/": {
      "get": {
        "tags": [
          "系统"
        ],
        "summary": "服务信息",
        "description": "返回服务基本信息与关键入口，便于健康检查。",
        "operationId": "root__get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": true,
                  "type": "object",
                  "title": "Response Root  Get"
                }
              }
            }
          }
        }
      }
    },
    "/health": {
      "get": {
        "tags": [
          "系统"
        ],
        "summary": "健康检查",
        "description": "存活探针。",
        "operationId": "health_health_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "additionalProperties": {
                    "type": "string"
                  },
                  "type": "object",
                  "title": "Response Health Health Get"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "AuthResponse": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "用户 UUID"
          },
          "username": {
            "type": "string",
            "title": "Username",
            "description": "用户名"
          },
          "email": {
            "type": "string",
            "title": "Email",
            "description": "邮箱"
          },
          "nickname": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nickname",
            "description": "昵称"
          },
          "avatar_url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Avatar Url",
            "description": "头像地址"
          },
          "created_at": {
            "type": "string",
            "format": "date-time",
            "title": "Created At",
            "description": "注册时间（ISO 8601 UTC）"
          },
          "token": {
            "$ref": "#/components/schemas/TokenResponse",
            "description": "令牌信息，便于前端一次取用"
          }
        },
        "type": "object",
        "required": [
          "id",
          "username",
          "email",
          "created_at",
          "token"
        ],
        "title": "AuthResponse",
        "description": "注册/登录响应：用户信息 + 令牌（供前端一次拿到完整上下文）。"
      },
      "ClipboardDeleteResponse": {
        "properties": {
          "success": {
            "type": "boolean",
            "title": "Success",
            "description": "操作是否成功",
            "default": true
          },
          "message": {
            "type": "string",
            "title": "Message",
            "description": "人类可读的结果说明"
          },
          "id": {
            "type": "string",
            "title": "Id",
            "description": "被删除的剪贴板项 UUID"
          }
        },
        "type": "object",
        "required": [
          "message",
          "id"
        ],
        "title": "ClipboardDeleteResponse",
        "description": "删除单条剪贴板项的响应。"
      },
      "ClipboardItemCreate": {
        "properties": {
          "content": {
            "type": "string",
            "maxLength": 100000,
            "minLength": 1,
            "title": "Content",
            "description": "剪贴板内容（阶段一为纯文本）"
          },
          "title": {
            "anyOf": [
              {
                "type": "string",
                "maxLength": 200
              },
              {
                "type": "null"
              }
            ],
            "title": "Title",
            "description": "标题。留空时由服务端自动生成，格式 `<用户名> · <月-日 时:分>`，例如 `demo · 10-02 14:30`"
          },
          "content_type": {
            "$ref": "#/components/schemas/ContentType",
            "description": "内容类型，阶段一固定 text",
            "default": "text"
          },
          "preview": {
            "anyOf": [
              {
                "type": "string",
                "maxLength": 500
              },
              {
                "type": "null"
              }
            ],
            "title": "Preview",
            "description": "预览文本；不传时由服务端截取正文生成"
          },
          "metadata": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Metadata",
            "description": "附加元信息，例如 {\"mime\": \"text/plain\", \"size\": 1024}"
          }
        },
        "type": "object",
        "required": [
          "content"
        ],
        "title": "ClipboardItemCreate",
        "description": "创建剪贴板项请求。"
      },
      "ClipboardItemList": {
        "properties": {
          "items": {
            "items": {
              "$ref": "#/components/schemas/ClipboardItemResponse"
            },
            "type": "array",
            "title": "Items",
            "description": "当前页数据"
          },
          "page": {
            "type": "integer",
            "minimum": 1.0,
            "title": "Page",
            "description": "当前页码，从 1 开始"
          },
          "size": {
            "type": "integer",
            "minimum": 1.0,
            "title": "Size",
            "description": "每页条数"
          },
          "total": {
            "type": "integer",
            "minimum": 0.0,
            "title": "Total",
            "description": "符合条件的总条数"
          },
          "pages": {
            "type": "integer",
            "minimum": 0.0,
            "title": "Pages",
            "description": "总页数"
          }
        },
        "type": "object",
        "required": [
          "items",
          "page",
          "size",
          "total",
          "pages"
        ],
        "title": "ClipboardItemList",
        "description": "剪贴板列表响应（携带分页元信息）。"
      },
      "ClipboardItemResponse": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "剪贴板项 UUID"
          },
          "user_id": {
            "type": "string",
            "title": "User Id",
            "description": "所属用户 UUID"
          },
          "title": {
            "type": "string",
            "title": "Title",
            "description": "标题，用户未填写时由服务端自动生成"
          },
          "content_type": {
            "$ref": "#/components/schemas/ContentType",
            "description": "内容类型"
          },
          "content": {
            "type": "string",
            "title": "Content",
            "description": "文字内容或文件 URL"
          },
          "preview": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Preview",
            "description": "预览文本"
          },
          "metadata": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "title": "Metadata",
            "description": "附加元信息"
          },
          "created_at": {
            "type": "string",
            "format": "date-time",
            "title": "Created At",
            "description": "创建时间（ISO 8601 UTC）"
          },
          "updated_at": {
            "type": "string",
            "format": "date-time",
            "title": "Updated At",
            "description": "最后更新时间（ISO 8601 UTC）"
          }
        },
        "type": "object",
        "required": [
          "id",
          "user_id",
          "title",
          "content_type",
          "content",
          "created_at",
          "updated_at"
        ],
        "title": "ClipboardItemResponse",
        "description": "剪贴板项对外表示。\n\n注意：`content_hash` 不对外暴露，仅服务端用于去重。"
      },
      "ContentType": {
        "type": "string",
        "enum": [
          "text",
          "image",
          "file"
        ],
        "title": "ContentType",
        "description": "剪贴板内容类型。阶段一仅实现 `text`。"
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "MessageResponse": {
        "properties": {
          "success": {
            "type": "boolean",
            "title": "Success",
            "description": "操作是否成功",
            "default": true
          },
          "message": {
            "type": "string",
            "title": "Message",
            "description": "人类可读的结果说明"
          }
        },
        "type": "object",
        "required": [
          "message"
        ],
        "title": "MessageResponse",
        "description": "通用消息响应（删除类接口）。"
      },
      "SortBy": {
        "type": "string",
        "enum": [
          "created_at",
          "updated_at"
        ],
        "title": "SortBy",
        "description": "列表排序字段。"
      },
      "SortOrder": {
        "type": "string",
        "enum": [
          "desc",
          "asc"
        ],
        "title": "SortOrder",
        "description": "排序方向。"
      },
      "TokenResponse": {
        "properties": {
          "access_token": {
            "type": "string",
            "title": "Access Token",
            "description": "JWT 访问令牌"
          },
          "token_type": {
            "type": "string",
            "title": "Token Type",
            "description": "令牌类型，固定 bearer",
            "default": "bearer"
          },
          "expires_in": {
            "type": "integer",
            "title": "Expires In",
            "description": "有效期（秒）"
          },
          "user": {
            "$ref": "#/components/schemas/UserResponse",
            "description": "当前登录用户"
          }
        },
        "type": "object",
        "required": [
          "access_token",
          "expires_in",
          "user"
        ],
        "title": "TokenResponse",
        "description": "登录/注册成功后返回的令牌。"
      },
      "UserLoginRequest": {
        "properties": {
          "username": {
            "type": "string",
            "title": "Username",
            "description": "用户名或邮箱"
          },
          "password": {
            "type": "string",
            "title": "Password",
            "description": "密码"
          }
        },
        "type": "object",
        "required": [
          "username",
          "password"
        ],
        "title": "UserLoginRequest",
        "description": "登录请求。"
      },
      "UserRegisterRequest": {
        "properties": {
          "username": {
            "type": "string",
            "maxLength": 32,
            "minLength": 3,
            "title": "Username",
            "description": "用户名，3-32 字符"
          },
          "email": {
            "type": "string",
            "maxLength": 254,
            "minLength": 3,
            "title": "Email",
            "description": "邮箱"
          },
          "password": {
            "type": "string",
            "maxLength": 72,
            "minLength": 6,
            "title": "Password",
            "description": "密码，6-72 字符（bcrypt 上限 72 字节）"
          }
        },
        "type": "object",
        "required": [
          "username",
          "email",
          "password"
        ],
        "title": "UserRegisterRequest",
        "description": "注册请求。"
      },
      "UserResponse": {
        "properties": {
          "id": {
            "type": "string",
            "title": "Id",
            "description": "用户 UUID"
          },
          "username": {
            "type": "string",
            "title": "Username",
            "description": "用户名"
          },
          "email": {
            "type": "string",
            "title": "Email",
            "description": "邮箱"
          },
          "nickname": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Nickname",
            "description": "昵称"
          },
          "avatar_url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Avatar Url",
            "description": "头像地址"
          },
          "created_at": {
            "type": "string",
            "format": "date-time",
            "title": "Created At",
            "description": "注册时间（ISO 8601 UTC）"
          }
        },
        "type": "object",
        "required": [
          "id",
          "username",
          "email",
          "created_at"
        ],
        "title": "UserResponse",
        "description": "用户公开信息。**绝不包含密码哈希**。"
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          },
          "input": {
            "title": "Input"
          },
          "ctx": {
            "type": "object",
            "title": "Context"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      }
    }
  },
  "tags": [
    {
      "name": "认证",
      "description": "注册、登录、获取当前用户。**第 4 步接入真实 JWT 后**才会校验凭证；当前所有接口都返回演示用户。"
    },
    {
      "name": "剪贴板",
      "description": "文字剪贴板的上传、列表、详情、删除。数据保存在进程内存中，**重启即重置为种子数据**（第 3 步接入 PostgreSQL 后消除）。"
    },
    {
      "name": "系统",
      "description": "健康检查与服务信息。"
    }
  ]
}
```