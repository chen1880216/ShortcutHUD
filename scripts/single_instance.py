"""单实例保护：同一 Windows 会话里只允许运行一个 ShortcutHUD。

没有这道保护时，用户双击几次快捷方式就会起多个进程：每个进程都会装键盘钩子、
注册全局热键（后起的注册失败）、各自弹浮窗，行为很难预期。

实现用命名内核互斥体（named mutex）：第一个进程创建它，后续进程创建时
`GetLastError()` 返回 `ERROR_ALREADY_EXISTS`，据此判定「已经在跑了」。
互斥体随进程退出自动释放，所以上一个实例崩溃也不会把锁留死。
"""

from __future__ import annotations

import sys

MUTEX_NAME = r"Local\ShortcutHUD.SingleInstance"
ERROR_ALREADY_EXISTS = 183

WINDOWS = sys.platform == "win32"


class SingleInstanceGuard:
    """进程级单实例闸门；`acquire()` 返回 False 表示已有实例在运行。"""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._name = name
        self._handle: int | None = None
        self._already_running = False

    @property
    def already_running(self) -> bool:
        """上一次 `acquire()` 是否发现已有实例（用于日志/退出码）。"""

        return self._already_running

    def acquire(self) -> bool:
        """尝试占用单实例锁；True 表示可以继续启动。"""

        if not WINDOWS:
            # 非 Windows 平台不做限制（本项目只发布 Windows 便携版）。
            self._already_running = False
            return True
        if self._handle is not None:
            return not self._already_running

        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self._name)
        error = ctypes.get_last_error()
        if not handle:
            # 创建失败（极罕见）时放行，避免程序完全起不来。
            self._already_running = False
            return True
        self._handle = int(handle)
        self._already_running = error == ERROR_ALREADY_EXISTS
        return not self._already_running

    def release(self) -> None:
        """释放锁（进程退出时会自动释放，这里只是让测试与显式关闭更干净）。"""

        handle = self._handle
        self._handle = None
        self._already_running = False
        if not handle or not WINDOWS:
            return
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CloseHandle(handle)

    def __enter__(self) -> "SingleInstanceGuard":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.release()
