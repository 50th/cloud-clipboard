import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    // 固定端口：浏览器剪贴板 API 只在 https 或 localhost/127.0.0.1 下可用
    port: 5173,
    strictPort: true,
  },
})
