# main.py
import sys
import os
import logging
import traceback
import warnings
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 忽略警告
warnings.filterwarnings('ignore', category=DeprecationWarning)

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
from PyQt6.QtCore import Qt, QObject, pyqtSignal
import ctypes

def get_log_dir():
    """获取日志目录 - exe目录优先，失败回退到用户目录"""
    # 判断是打包后的exe还是源码运行
    if getattr(sys, 'frozen', False):
        # 打包后的exe
        exe_dir = Path(sys.executable).parent
    else:
        # 源码运行
        exe_dir = Path(__file__).parent
    
    # 尝试exe所在目录
    log_dir = exe_dir / "logs"
    
    try:
        log_dir.mkdir(exist_ok=True)
        # 测试写入权限
        test_file = log_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return log_dir
    except (PermissionError, OSError):
        # 无权限则回退到用户目录
        fallback_dir = Path.home() / "sectool_logs"
        fallback_dir.mkdir(exist_ok=True)
        return fallback_dir

# 配置日志输出到文件
log_dir = get_log_dir()
log_file = log_dir / f"sectool_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 配置日志 - 修复Logging error问题
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8', mode='w')
    ]
)
logger = logging.getLogger(__name__)

# 添加控制台处理器（避免重定向导致的循环）
console_handler = logging.StreamHandler(sys.__stdout__)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logging.getLogger().addHandler(console_handler)

logger.info(f"="*60)
logger.info(f"日志文件位置: {log_file}")
logger.info(f"Python版本: {sys.version}")
logger.info(f"工作目录: {Path.cwd()}")
logger.info(f"可执行文件: {sys.executable}")
logger.info(f"="*60)

# 异常钩子记录未捕获的异常
original_excepthook = sys.excepthook
def exception_hook(exc_type, exc_value, exc_traceback):
    logger.error("="*60)
    logger.error("未捕获的异常:")
    logger.error("="*60)
    logger.error("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    logger.error("="*60)
    # 调用原始异常钩子
    original_excepthook(exc_type, exc_value, exc_traceback)

sys.excepthook = exception_hook

from core.network_monitor import NetworkMonitor
from core.autoruns_parser import AutorunsParser
from core.data_store import DataStore
from core.search_service import SearchService

from ui.network_tab import NetworkTab
from ui.autoruns_tab import AutorunsTab
from ui.workspace_tab import WorkspaceTab

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("终端安全检测工具 v1.0")
        self.setMinimumSize(1200, 700)
        
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
    # 检查管理员权限
    if not is_admin():
        # 尝试提权重启
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit(0)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
