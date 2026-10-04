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
    // ⚠️ 端口不能随意改回 5173：Windows 保留了 5141-5240 区间（Hyper-V/WSL/Docker 常见），
    // 落在该区间的端口会报 EACCES / WinError 10013 而无法绑定。
    // 排查命令：netsh int ipv4 show excludedportrange protocol=tcp
    // 仍用 127.0.0.1 而非局域网 IP：浏览器剪贴板 API 只在 https 或 localhost 下可用。
    port: 5273,
    strictPort: true,
  },
})
