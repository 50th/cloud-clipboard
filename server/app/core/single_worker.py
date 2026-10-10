"""单 worker 强制守卫。

**为什么必须拦下多 worker**：WebSocket 的连接表（`app/services/ws_manager.py`）
是**进程内**结构。多 worker 时用户 A 连 worker 1、用户 B 连 worker 2，
事件永远送不到；而数据库是共享的，所以 **数据一致、推送不一致**——
现象隐蔽、极难排查。见 `docs/ws-protocol.md` 的「多实例问题」。

**为什么不能只看环境变量**：uvicorn 的 `--workers N`（CLI）与 `WEB_CONCURRENCY=N`
（环境变量）是两条独立路径，**CLI 的 `--workers` 不会写进环境变量**（实测：worker
进程里 `WEB_CONCURRENCY` 是 `None`）。只查环境变量会漏掉最常见的手误。

## 检测机制：固定端口独占

启动时绑定一个**固定**的回环端口并一直握着套接字。第二个实例绑定时会拿到
`WSAEADDRINUSE (10048)`，据此确定"已有实例在跑"。

⚠️ **端口必须是固定的，不能用 `bind(('127.0.0.1', 0))` 去"找一个空闲端口"。**
实测：`bind(0)` 每次都返回**不同**的端口（同一进程内连续三次得到 13099/13100/13101），
因此"探测空闲端口再绑定"的写法在并发下**永远不会冲突**，锁形同虚设。
这一点很容易被后人"优化"错，故特别注明。
"""

from __future__ import annotations

import os
import socket

# 锁端口必须固定。取一个不常用的高位端口，降低与其他软件撞车的概率。
LOCK_PORT = 49_137

# 抢到的端口号；None 表示尚未抢或已释放。
_locked_port: int | None = None
# ⚠️ 必须保存在模块级：套接字一旦被回收，端口立即释放，守卫随即失效。
_lock_socket: socket.socket | None = None


class MultipleWorkersError(RuntimeError):
    """检测到本机已有另一个实例在运行（多半是多 worker 启动）。"""


def lock_single_worker(port: int | None = None) -> int:
    """独占单实例锁端口，返回该端口号。重复调用是幂等的。

    `port` 为 None 时使用模块级 `LOCK_PORT`（生产行为）。之所以在函数体内而不是
    用默认参数读取 `LOCK_PORT`，是为了让测试能 monkeypatch 它——默认参数在函数
    定义时就求值了，patch 模块属性不会生效。
    """
    global _locked_port, _lock_socket

    if _lock_socket is not None and _locked_port is not None:
        return _locked_port

    target = LOCK_PORT if port is None else port

    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows：禁止其他进程用 SO_REUSEADDR 抢绑同一端口
            lock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        lock.bind(("127.0.0.1", target))
    except OSError as exc:
        lock.close()
        raise MultipleWorkersError(
            f"单实例锁端口 {target} 已被占用，说明本机已有另一个 Cloud Clipboard 实例在运行。"
        ) from exc

    _lock_socket = lock
    _locked_port = target
    return target


def release_single_worker() -> None:
    """释放锁（进程退出时调用；也用于测试）。"""
    global _locked_port, _lock_socket
    if _lock_socket is not None:
        try:
            _lock_socket.close()
        except OSError:  # pragma: no cover - 关闭失败无需处理
            pass
    _lock_socket = None
    _locked_port = None


def locked_port() -> int | None:
    """当前持有的锁端口号（未持有时为 None）。"""
    return _locked_port


def assert_single_worker() -> int:
    """启动守卫：先检查 `WEB_CONCURRENCY` 给出更友好的提示，再做锁端口检测。

    返回持有的锁端口号（供启动日志使用）；检测到多 worker 时抛
    `MultipleWorkersError`。
    """
    raw = os.environ.get("WEB_CONCURRENCY")
    if raw is not None and raw.strip():
        try:
            workers = int(raw)
        except ValueError:
            raise MultipleWorkersError(
                f"WEB_CONCURRENCY 不是合法整数: {raw!r}"
            ) from None
        if workers > 1:
            _banner(f"WEB_CONCURRENCY={workers}")
            raise MultipleWorkersError(
                f"WEB_CONCURRENCY={workers}：WebSocket 广播是进程内实现，"
                "不能以多 worker 运行。"
            )

    try:
        return lock_single_worker()
    except MultipleWorkersError as exc:
        _banner(str(exc))
        raise


def _banner(reason: str) -> None:
    """打印醒目横幅。

    uvicorn 的 supervisor 会**反复重启**崩溃的 worker，只抛异常的话报错很容易被
    淹没在重复日志里，所以额外打一条显眼的横幅。
    """
    print(
        f"\n{'=' * 68}\n"
        f"[致命] 检测到多 worker / 多实例：{reason}\n"
        "  WebSocket 广播是**进程内**实现：多 worker 时 A 连 worker 1、\n"
        "  B 连 worker 2，事件永远送不到；而数据库是共享的，所以\n"
        "  **数据一致、推送不一致**，现象隐蔽且极难排查。\n"
        "  请用 --workers 1 启动。确需多副本时，先给广播加上\n"
        "  Redis Pub/Sub（见 docs/ws-protocol.md 的「多实例问题」）。\n"
        f"{'=' * 68}",
        flush=True,
    )
