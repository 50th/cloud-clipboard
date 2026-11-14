"""进程内滑动窗口限流。

单 worker 已由启动守卫保证（见 `app/core/single_worker.py`），
因此进程内计数有效；引入多 worker 前必须先换成 Redis。
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, status

# key → 最近窗口内的请求时间戳（单调时钟）
_WINDOWS: dict[str, deque[float]] = {}
_LOCK = Lock()


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """记录一次访问；超出窗口额度时抛 429，并带 `Retry-After`。"""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _WINDOWS.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="尝试过于频繁，请稍后再试",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def clear_rate_limit(key: str) -> None:
    """清空某个键的计数（密码校验成功后调用）。"""
    with _LOCK:
        _WINDOWS.pop(key, None)


def reset_rate_limits() -> None:
    """清空全部计数；测试隔离用。"""
    with _LOCK:
        _WINDOWS.clear()
