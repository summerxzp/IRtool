from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer
from PyQt6.QtWidgets import QMessageBox
import subprocess
import threading
import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

from core.constants import MAX_THREAD_COUNT

LOGGER = logging.getLogger(__name__)


class CommandStatus(Enum):
    """命令执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CommandResult:
    """命令执行结果"""
    status: CommandStatus
    return_code: int
    stdout: str
    stderr: str
    error_message: Optional[str] = None


class CommandTask(QRunnable):
    """命令执行任务"""
    
    def __init__(self, command: str, callback: Optional[Callable[[CommandResult], None]] = None):
        """
        初始化命令任务
        
        Args:
            command: 要执行的命令
            callback: 完成回调函数
        """
        super().__init__()
        self.command = command
        self.callback = callback
        self._is_cancelled = False
        self._lock = threading.Lock()
    
    def run(self):
        """执行命令"""
        if self._is_cancelled:
            result = CommandResult(
                status=CommandStatus.CANCELLED,
                return_code=-1,
                stdout="",
                stderr="",
                error_message="任务已取消"
            )
        else:
            result = self._execute_command()
        
        # 在主线程中调用回调
        if self.callback:
            QTimer.singleShot(0, lambda: self.callback(result))
    
    def _execute_command(self) -> CommandResult:
        """执行命令并返回结果"""
        LOGGER.debug(f"[SafeExecutor] 开始执行命令: {self.command}")
        
        try:
            process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            stdout, stderr = process.communicate()
            return_code = process.returncode
            
            LOGGER.debug(f"[SafeExecutor] 命令执行完成，返回码: {return_code}")
            LOGGER.debug(f"[SafeExecutor] 标准输出: {stdout}")
            LOGGER.debug(f"[SafeExecutor] 标准错误: {stderr}")
            
            # 检查错误：返回码非零，或 stderr 包含错误关键词
            error_keywords = ['拒绝访问', 'access denied', 'error', '失败', 'failed', 'cannot', '无法']
            has_error_in_stderr = stderr and any(kw in stderr.lower() for kw in error_keywords)
            
            if return_code == 0 and not has_error_in_stderr:
                status = CommandStatus.SUCCESS
            else:
                status = CommandStatus.FAILED
            
            return CommandResult(
                status=status,
                return_code=return_code,
                stdout=stdout,
                stderr=stderr
            )
        except PermissionError as e:
            LOGGER.warning(f"[SafeExecutor] 权限错误: {str(e)}")
            return CommandResult(
                status=CommandStatus.FAILED,
                return_code=-1,
                stdout="",
                stderr="",
                error_message=f"权限不足: {str(e)}"
            )
        except FileNotFoundError as e:
            LOGGER.warning(f"[SafeExecutor] 文件未找到: {str(e)}")
            return CommandResult(
                status=CommandStatus.FAILED,
                return_code=-1,
                stdout="",
                stderr="",
                error_message=f"命令或文件不存在: {str(e)}"
            )
        except Exception as e:
            LOGGER.error(f"[SafeExecutor] 执行异常: {str(e)}", exc_info=True)
            return CommandResult(
                status=CommandStatus.FAILED,
                return_code=-1,
                stdout="",
                stderr="",
                error_message=f"执行失败: {str(e)}"
            )
    
    def cancel(self):
        """取消任务"""
        with self._lock:
            self._is_cancelled = True


class SafeExecutor(QObject):
    """安全执行器 - 集中处理权限、输出、错误"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(MAX_THREAD_COUNT)
        self.current_tasks = []
    
    def execute(self, command: str, callback: Optional[Callable[[CommandResult], None]] = None,
               show_ui: bool = True) -> bool:
        """
        执行命令
        
        Args:
            command: 要执行的命令
            callback: 完成回调函数
            show_ui: 是否显示 UI 提示
            
        Returns:
            是否成功启动任务
        """
        from PyQt6.QtWidgets import QApplication
        
        if not command:
            if show_ui:
                parent = QApplication.activeWindow()
                QMessageBox.warning(parent, "警告", "命令为空")
            return False
        
        if show_ui:
            parent = QApplication.activeWindow()
            reply = QMessageBox.question(
                parent,
                "确认执行",
                f"确定要执行以下命令吗？\n\n{command}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False
        
        task = CommandTask(command, callback)
        self.current_tasks.append(task)
        self.thread_pool.start(task)
        
        return True
    
    def execute_silent(self, command: str, callback: Optional[Callable[[CommandResult], None]] = None) -> bool:
        """
        静默执行命令（不显示确认对话框）
        
        Args:
            command: 要执行的命令
            callback: 完成回调函数
            
        Returns:
            是否成功启动任务
        """
        return self.execute(command, callback, show_ui=False)
    
    def cancel_all(self):
        """取消所有任务"""
        for task in self.current_tasks:
            task.cancel()
        self.current_tasks.clear()
    
    def wait_for_all(self):
        """等待所有任务完成"""
        self.thread_pool.waitForDone()
    
    def cleanup(self):
        """清理资源"""
        self.cancel_all()
        self.thread_pool.clear()
