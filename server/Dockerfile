# 云剪贴板后端生产镜像。
# 迁移不在镜像构建期执行：由部署流程单独运行 `alembic upgrade head`。
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 非 root 运行
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN mkdir -p logs && chown -R app:app /app

USER app

EXPOSE 8000

# ⚠️ 不传 --workers：WebSocket 广播是进程内实现，多 worker 会丢推送事件
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
