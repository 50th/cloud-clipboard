/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_WS_URL?: string
  readonly VITE_AUTH_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** 构建时注入的应用版本号（发布 Tag 或 package.json version） */
declare const __APP_VERSION__: string
