# main.py
"""IRtool 应用入口"""

# 标准库
import ctypes
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 第三方库
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox

# 本地模块（需要先确定 APP_DIR）
def get_app_dir():
    """获取应用根目录（支持源码运行和PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

APP_DIR = get_app_dir()
sys.path.insert(0, str(APP_DIR))

from core.network_monitor import NetworkMonitor
from core.autoruns_parser import AutorunsParser
from core.data_store import DataStore
from core.search_service import SearchService
from core.constants import (
    APP_NAME, APP_ID, APP_VERSION, BUILD_TYPE, BUILD_DATE,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, LOG_FORMAT, LOG_LEVEL
)

from ui.network_tab import NetworkTab
from ui.autoruns_tab import AutorunsTab
# from ui.skill_scan_tab import SkillScanTab  # 暂时隐藏 Skill Scan Tab
from ui.workspace_tab import WorkspaceTab

# 创建logs目录
logs_dir = APP_DIR / "logs"
logs_dir.mkdir(exist_ok=True)

# 配置日志输出到文件（使用logs目录）
log_file = logs_dir / f"IRtool_{datetime.now().strftime('%Y%m%d')}.log"

# 创建logger
logger = logging.getLogger('IRtool')
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 文件处理器
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(LOG_FORMAT)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 注意：不再添加 StreamHandler 到 stdout，避免与 PrintLogger 递归
# 控制台输出通过 PrintLogger 单独处理

# 重定向 print 到日志（避免递归）
class PrintLogger:
    def __init__(self, log_func, original_stdout):
        self.log_func = log_func
        self.original_stdout = original_stdout
        self.buffer = ""
    
    def write(self, message):
        # 直接写入原始stdout（如果可用），避免递归
        if self.original_stdout and hasattr(self.original_stdout, 'write'):
            try:
                self.original_stdout.write(message)
            except:
                pass
        # 同时记录到日志
        self.buffer += message
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            for line in lines[:-1]:
                if line.strip():
                    self.log_func(line)
            self.buffer = lines[-1]
    
    def flush(self):
        if self.original_stdout and hasattr(self.original_stdout, 'flush'):
            try:
                self.original_stdout.flush()
            except:
                pass
        if self.buffer.strip():
            self.log_func(self.buffer)
            self.buffer = ""

# 保存原始stdout/stderr
_original_stdout = sys.stdout
_original_stderr = sys.stderr

# 替换 stdout/stderr
sys.stdout = PrintLogger(logger.info, _original_stdout)
sys.stderr = PrintLogger(logger.error, _original_stderr)

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self, is_admin_mode=True):
        super().__init__()

        self.is_admin_mode = is_admin_mode
        title = f"IRtool v{APP_VERSION}"
        if not is_admin_mode:
            title += " (非管理员模式)"
        logger.info(f"[MainWindow] Setting title: {title}, is_admin_mode={is_admin_mode}")
        self.setWindowTitle(title)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        
        # 初始化核心模块
        self._init_modules()
        
        # 初始化UI
        self._init_ui()
    
    def _init_modules(self):
        """初始化核心模块"""
        self.network_monitor = NetworkMonitor()
        self.data_store = DataStore()
        self.search_service = SearchService(self.data_store)
        
        try:
            self.autoruns_parser = AutorunsParser()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "警告", str(e))
            self.autoruns_parser = None
    
    def _init_ui(self):
        """初始化UI"""
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # 网络监控标签
        self.network_tab = NetworkTab(self.network_monitor, self.data_store)
        tabs.addTab(self.network_tab, "网络监控")

        # Skill Scan 标签（独立于 Autoruns/Workspace）- 暂时隐藏
        # self.skill_scan_tab = SkillScanTab()
        # tabs.addTab(self.skill_scan_tab, "Skill Scan")

        # 持久化检测标签
        if self.autoruns_parser:
            self.autoruns_tab = AutorunsTab(self.autoruns_parser, self.data_store)
            tabs.addTab(self.autoruns_tab, "持久化检测")
            
            # 工作台标签
            self.workspace_tab = WorkspaceTab(self.data_store, self.search_service)
            tabs.addTab(self.workspace_tab, "工作台")
            
            # 连接信号：Autoruns -> Workspace
            self.autoruns_tab.search_in_workspace.connect(self._on_search_in_workspace)
            # 连接信号：Workspace -> Autoruns
            self.workspace_tab.jump_to_autorun.connect(self._on_workspace_jump_to_autorun)
    
    def _on_search_in_workspace(self, search_text):
        """处理来自 Autoruns Tab 的搜索请求"""
        if not hasattr(self, 'workspace_tab'):
            return
        
        # 切换到工作台 Tab
        tabs = self.centralWidget()
        if isinstance(tabs, QTabWidget):
            for i in range(tabs.count()):
                if tabs.tabText(i) == "工作台":
                    tabs.setCurrentIndex(i)
                    break
        
        # 执行搜索
        self.workspace_tab.search(search_text)

    def _on_workspace_jump_to_autorun(self, entry):
        """处理来自 Workspace 的跳转请求"""
        if not hasattr(self, 'autoruns_tab') or not self.autoruns_tab:
            return
        
        # 切换到持久化检测 Tab
        tabs = self.centralWidget()
        if isinstance(tabs, QTabWidget):
            for i in range(tabs.count()):
                if tabs.tabText(i) == "持久化检测":
                    tabs.setCurrentIndex(i)
                    break
        self.autoruns_tab.jump_to_entry(entry)
    
    def closeEvent(self, event):
        """应用程序关闭事件处理"""
        # 停止网络监控
        if hasattr(self, 'network_monitor'):
            self.network_monitor.stop_monitoring()
        
        # 停止autoruns扫描（如果正在进行）
        if hasattr(self, 'autoruns_tab') and self.autoruns_tab:
            self.autoruns_tab.cleanup()
        
        event.accept()

def main():
    # 输出启动信息
    logger.info("[Startup] ========================================")
    logger.info(f"[Startup] AppID: {APP_ID}")
    logger.info(f"[Startup] Version: {APP_VERSION}")
    logger.info(f"[Startup] Build: {BUILD_TYPE} ({BUILD_DATE})")
    logger.info(f"[Startup] App Directory: {APP_DIR}")
    logger.info("[Startup] ========================================")

    # 检查管理员权限
    is_admin_mode = is_admin()
    logger.info(f"[Main] Admin check: is_admin_mode={is_admin_mode}")
    
    # 尝试申请管理员权限，但如果失败也能继续运行
    if not is_admin_mode:
        try:
            logger.info("[Main] Attempting to elevate privileges...")
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            logger.info(f"[Main] ShellExecuteW result: {result}")
            # 如果提权成功（用户点击"是"），退出当前进程，让新进程接管
            if result > 32:
                logger.info("[Main] Elevation requested, exiting current process")
                sys.exit(0)
            # 如果提权失败或被拒绝，继续以非管理员模式运行
            logger.info("[Main] Elevation failed or denied, continuing without admin")
        except Exception as e:
            logger.warning(f"[Main] Elevation attempt failed: {e}, continuing without admin")
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格
    
    window = MainWindow(is_admin_mode=is_admin_mode)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
