# main.py
"""IRtool 应用入口"""

# 标准库
import ctypes
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

# 第三方库
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QMessageBox
)

# 本地模块（需要先确定 APP_DIR）
# 使用统一的路径解析工具
from utils.path_resolver import get_app_dir
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
from ui.log_collector_tab import LogCollectorTab

# 创建logs目录
logs_dir = APP_DIR / "logs"
logs_dir.mkdir(exist_ok=True)

# 配置日志输出到文件（使用logs目录）
log_file = logs_dir / f"IRtool_{datetime.now().strftime('%Y%m%d')}.log"

# 创建logger
logger = logging.getLogger('IRtool')
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 文件处理器（带轮转，单文件最大 10MB，保留 5 个备份）
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
)
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
            except Exception:
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
            except Exception:
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
    except Exception:
        return False


def _ensure_single_instance():
    """单实例互斥锁，防止重复启动"""
    mutex_name = f"Global\\{APP_ID}"
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:
        logger.warning("[Startup] 检测到已有实例运行，尝试激活已有窗口后退出")
        hwnd = ctypes.windll.user32.FindWindowW(None, f"IRtool v{APP_VERSION}")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        sys.exit(0)
    return _mutex


def run_as_admin():
    """以管理员权限重新启动自身，返回是否成功发起提权"""
    import subprocess
    if getattr(sys, 'frozen', False):
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        params = subprocess.list2cmdline([sys.argv[0]] + sys.argv[1:])

    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret <= 32:
        logger.error(f"[Startup] 提权失败，ShellExecuteW 返回值: {ret}")
        return False
    sys.exit(0)


class MainWindow(QMainWindow):
    """主窗口"""

    # IDE 风格 Tab 按钮样式
    _TAB_BTN_STYLE = """
    QPushButton {
        border: none;
        background: transparent;
        color: #6b7280;
        font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
        font-size: 13px;
        font-weight: 500;
        padding: 8px 18px;
        border-radius: 6px;
        margin: 2px 2px;
    }
    QPushButton:hover {
        background: rgba(76, 141, 255, 0.08);
        color: #3a3f47;
    }
    QPushButton:checked {
        background: #4c8dff;
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton:checked:hover {
        background: #3a7af0;
    }
    """

    _TAB_BAR_STYLE = """
    QWidget#tabBar {
        background: #ffffff;
        border-bottom: 1px solid #dce1e8;
    }
    """

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
        """初始化UI - IDE风格顶部导航"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab 导航栏
        self.tab_bar = QWidget()
        self.tab_bar.setObjectName("tabBar")
        self.tab_bar.setStyleSheet(self._TAB_BAR_STYLE)
        self.tab_bar_layout = QHBoxLayout(self.tab_bar)
        self.tab_bar_layout.setContentsMargins(8, 4, 8, 4)
        self.tab_bar_layout.setSpacing(4)
        self.tab_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # StackedWidget 用于切换页面
        self.stack = QStackedWidget()

        # Tab 按钮列表
        self._tab_buttons = []

        # 网络监控
        self.network_tab = NetworkTab(self.network_monitor, self.data_store)
        self._add_tab("网络监控", self.network_tab)

        # 日志采集
        self.log_collector_tab = LogCollectorTab(self.data_store)
        self._add_tab("日志采集", self.log_collector_tab)

        # 持久化检测 + 工作台
        if self.autoruns_parser:
            self.autoruns_tab = AutorunsTab(self.autoruns_parser, self.data_store)
            self._add_tab("持久化检测", self.autoruns_tab)

            self.workspace_tab = WorkspaceTab(self.data_store, self.search_service)
            self._add_tab("工作台", self.workspace_tab)

            self.autoruns_tab.search_in_workspace.connect(self._on_search_in_workspace)
            self.workspace_tab.jump_to_autorun.connect(self._on_workspace_jump_to_autorun)

        self.tab_bar_layout.addStretch()
        main_layout.addWidget(self.tab_bar)
        main_layout.addWidget(self.stack)

        # 默认选中第一个
        if self._tab_buttons:
            self._tab_buttons[0].setChecked(True)
    
    def _add_tab(self, title: str, widget: QWidget):
        """添加一个Tab页面"""
        btn = QPushButton(title)
        btn.setCheckable(True)
        btn.setStyleSheet(self._TAB_BTN_STYLE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(34)
        btn.clicked.connect(lambda checked, b=btn: self._on_tab_clicked(b))

        self.tab_bar_layout.insertWidget(len(self._tab_buttons), btn)
        self._tab_buttons.append(btn)
        self.stack.addWidget(widget)
    
    def _on_tab_clicked(self, clicked_btn: QPushButton):
        """Tab按钮点击事件"""
        for i, btn in enumerate(self._tab_buttons):
            if btn is clicked_btn:
                btn.setChecked(True)
                self.stack.setCurrentIndex(i)
            else:
                btn.setChecked(False)
    
    def _switch_to_tab(self, title: str):
        """切换到指定标题的Tab"""
        for i, btn in enumerate(self._tab_buttons):
            if btn.text() == title:
                btn.setChecked(True)
                self.stack.setCurrentIndex(i)
            else:
                btn.setChecked(False)
    
    def _on_search_in_workspace(self, search_text):
        """处理来自 Autoruns Tab 的搜索请求"""
        if not hasattr(self, 'workspace_tab'):
            return
        self._switch_to_tab("工作台")
        self.workspace_tab.search(search_text)
    
    def _on_workspace_jump_to_autorun(self, entry):
        """处理来自 Workspace 的跳转请求"""
        if not hasattr(self, 'autoruns_tab') or not self.autoruns_tab:
            return
        self._switch_to_tab("持久化检测")
        self.autoruns_tab.jump_to_entry(entry)
    
    def closeEvent(self, event):
        """应用程序关闭事件处理"""
        # 停止网络监控
        if hasattr(self, 'network_monitor'):
            self.network_monitor.stop_monitoring()
        
        # 停止日志采集
        if hasattr(self, 'log_collector_tab') and self.log_collector_tab:
            self.log_collector_tab.cleanup()
        
        # 停止autoruns扫描（如果正在进行）
        if hasattr(self, 'autoruns_tab') and self.autoruns_tab:
            self.autoruns_tab.cleanup()
        
        event.accept()

def _global_exception_hook(exc_type, exc_value, exc_tb):
    logger.error("[UncaughtException] 未捕获的异常", exc_info=(exc_type, exc_value, exc_tb))


def main():
    sys.excepthook = _global_exception_hook

    # 单实例检测
    _mutex = _ensure_single_instance()

    # 输出启动信息
    logger.info("[Startup] ========================================")
    logger.info(f"[Startup] AppID: {APP_ID}")
    logger.info(f"[Startup] Version: {APP_VERSION}")
    logger.info(f"[Startup] Build: {BUILD_TYPE} ({BUILD_DATE})")
    logger.info(f"[Startup] App Directory: {APP_DIR}")
    logger.info("[Startup] ========================================")

    # 检查管理员权限，非管理员则自动提权重启
    admin_mode = is_admin()
    if not admin_mode:
        logger.warning("[Startup] 未以管理员权限运行，尝试提权重启...")
        if not run_as_admin():
            logger.warning("[Startup] 提权失败，以非管理员模式继续运行")
            admin_mode = False

    # 创建应用
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 加载全局样式
    from ui.ui_style import apply_flat_style
    apply_flat_style(app)

    # 全局设置 Tooltip 调色板，确保所有弹窗中的 tooltip 颜色一致
    from PyQt6.QtWidgets import QToolTip
    tip_palette = QPalette()
    tip_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    tip_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#2b2f33"))
    QToolTip.setPalette(tip_palette)

    # 创建主窗口
    window = MainWindow(is_admin_mode=admin_mode)
    window.show()

    logger.info("[Startup] 主窗口已显示")

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
