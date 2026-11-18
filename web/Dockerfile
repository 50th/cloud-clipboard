# 云剪贴板 Web 端生产镜像：多阶段构建，Nginx 托管静态文件。
# Nginx 配置由 deploy/docker-compose.prod.yml 挂载，不在本镜像内。

FROM node:24-alpine AS build

WORKDIR /app

RUN npm install -g pnpm@11.7.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .

# 可选：留空时前端运行时使用当前访问的域名与端口（推荐）
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN pnpm build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
