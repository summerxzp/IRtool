# main.py
import sys
import os
import logging
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
from PyQt6.QtCore import Qt
import ctypes

from core.network_monitor import NetworkMonitor
from core.autoruns_parser import AutorunsParser
from core.data_store import DataStore
from core.search_service import SearchService

from ui.network_tab import NetworkTab
from ui.autoruns_tab import AutorunsTab
from ui.workspace_tab import WorkspaceTab

# 配置日志输出到文件
log_file = Path(__file__).parent / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 重定向 print 到日志
class PrintLogger:
    def __init__(self, logger):
        self.logger = logger
    
    def write(self, message):
        if message.strip():
            self.logger.info(message.rstrip())
    
    def flush(self):
        pass

# 替换 print
sys.stdout = PrintLogger(logging.getLogger())
sys.stderr = PrintLogger(logging.getLogger())

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
        title = "终端安全检测工具 v1.0"
        if not is_admin_mode:
            title += " (非管理员模式)"
        self.setWindowTitle(title)
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
    is_admin_mode = is_admin()
    if not is_admin_mode:
        # 尝试提权重启，但如果用户拒绝则继续以非管理员模式运行
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        # 如果用户点击了"是"接受UAC，ShellExecuteW会返回一个大于32的值
        # 如果用户点击"否"拒绝UAC，返回值为SE_ERR_ACCESSDENIED (5)
        # 如果提权成功，当前进程应该退出，让新进程接管
        # 如果提权失败或被拒绝，继续以非管理员模式运行
        if result > 32:
            # 提权请求已发送，退出当前进程
            sys.exit(0)
        # 如果 result <= 32，表示提权失败，继续以非管理员模式运行
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion风格
    
    window = MainWindow(is_admin_mode=is_admin_mode)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
