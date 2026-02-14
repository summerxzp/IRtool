import logging
import os
import time
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

LOGGER = logging.getLogger("IRtool.autoruns_scan")
DEBUG_LOG_ENABLED = os.getenv("IRTOOL_DEBUG_LOG", "0") == "1"


def _debug_log(msg: str):
    if DEBUG_LOG_ENABLED:
        LOGGER.debug(msg)


class AutorunsScanWorker(QThread):
    """扫描工作线程"""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, parser, include_hash: bool, verify_sig: bool, category_filter):
        super().__init__()
        self.parser = parser
        self.include_hash = include_hash
        self.verify_sig = verify_sig
        self.category_filter = category_filter
        self._is_cancelled = False

    def cancel(self):
        """取消扫描"""
        self._is_cancelled = True

    def run(self):
        try:
            _debug_log(
                f"[ScanThread] 开始扫描，include_hash={self.include_hash}, "
                f"verify_sig={self.verify_sig}"
            )
            self.progress.emit("正在扫描自启动项...")
            entries = self.parser.scan(
                include_hash=self.include_hash,
                verify_signature=self.verify_sig,
                category_filter=self.category_filter,
            )
            _debug_log(f"[ScanThread] 扫描完成，共 {len(entries)} 个条目")

            if not self._is_cancelled:
                _debug_log("[ScanThread] 转换为字典格式")
                entries_dict = [e.to_dict() for e in entries]
                _debug_log("[ScanThread] 发送 finished 信号")
                self.finished.emit(entries_dict)
            else:
                _debug_log("[ScanThread] 扫描已取消")
        except Exception as exc:
            import traceback

            error_msg = str(exc)
            error_trace = traceback.format_exc()
            _debug_log(f"[ScanThread] 扫描错误: {error_msg}")
            _debug_log(f"[ScanThread] 错误堆栈:\n{error_trace}")
            if not self._is_cancelled:
                self.error.emit(error_msg)


class AutorunsScanController(QObject):
    """扫描状态机控制器：封装 worker 生命周期与状态切换"""

    scan_started = pyqtSignal()
    scan_progress = pyqtSignal(str, int)  # message, elapsed_seconds
    scan_finished = pyqtSignal(list, int)  # data, elapsed_seconds
    scan_error = pyqtSignal(str, int)  # error_msg, elapsed_seconds
    scan_cancelled = pyqtSignal(int)  # elapsed_seconds

    def __init__(self, parser, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.parser = parser
        self.current_worker: Optional[AutorunsScanWorker] = None
        self._is_scanning = False
        self._scan_start_time: Optional[float] = None

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    def start_scan(self, include_hash: bool, verify_sig: bool, category_filter=None) -> bool:
        """启动一次扫描。若已在扫描中则直接返回 False。"""
        if self._is_scanning:
            return False

        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(5000)
            self.current_worker = None

        self._is_scanning = True
        self._scan_start_time = time.time()
        self.scan_started.emit()

        worker = AutorunsScanWorker(
            parser=self.parser,
            include_hash=include_hash,
            verify_sig=verify_sig,
            category_filter=category_filter,
        )
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        self.current_worker = worker
        worker.start()
        return True

    def cancel_scan(self):
        """取消当前扫描并重置状态。"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(5000)
        self.current_worker = None

        self._is_scanning = False
        elapsed = self._elapsed_seconds()
        self._scan_start_time = None
        self.scan_cancelled.emit(elapsed)

    def cleanup(self):
        """窗口销毁时清理线程资源，不触发 UI 状态信号。"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(5000)
        self.current_worker = None
        self._is_scanning = False
        self._scan_start_time = None

    def _on_worker_progress(self, message: str):
        if self.sender() is not self.current_worker:
            return
        self.scan_progress.emit(message, self._elapsed_seconds())

    def _on_worker_finished(self, data):
        if self.sender() is not self.current_worker:
            return
        self._is_scanning = False
        elapsed = self._elapsed_seconds()
        self._scan_start_time = None
        self.current_worker = None
        self.scan_finished.emit(data, elapsed)

    def _on_worker_error(self, error_msg: str):
        if self.sender() is not self.current_worker:
            return
        self._is_scanning = False
        elapsed = self._elapsed_seconds()
        self._scan_start_time = None
        self.current_worker = None
        self.scan_error.emit(error_msg, elapsed)

    def _elapsed_seconds(self) -> int:
        if self._scan_start_time is None:
            return 0
        return int(time.time() - self._scan_start_time)
