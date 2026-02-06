#!/usr/bin/env python3
# debug_main.py - Debug version of main to catch errors
import sys
import traceback
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    print("Starting debug...")
    
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
    from PyQt6.QtCore import Qt
    import ctypes

    print("Qt imports successful")
    
    from core.network_monitor import NetworkMonitor
    from core.autoruns_parser import AutorunsParser

    from ui.network_tab import NetworkTab
    from ui.autoruns_tab import AutorunsTab
    
    print("Module imports successful")
    
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
            print("Initializing network monitor...")
            self.network_monitor = NetworkMonitor()
            print("Network monitor initialized")
            

            
            print("Initializing autoruns parser...")
            try:
                self.autoruns_parser = AutorunsParser()
                print("Autoruns parser initialized")
            except FileNotFoundError as e:
                print(f"Autoruns parser error: {e}")
                QMessageBox.warning(self, "警告", str(e))
                self.autoruns_parser = None
        
        def _init_ui(self):
            """初始化UI"""
            print("Initializing UI...")
            tabs = QTabWidget()
            self.setCentralWidget(tabs)
            
            # 网络监控标签
            print("Creating network tab...")
            self.network_tab = NetworkTab(self.network_monitor)
            tabs.addTab(self.network_tab, "网络监控")
            
            # 持久化检测标签
            if self.autoruns_parser:
                print("Creating autoruns tab...")
                self.autoruns_tab = AutorunsTab(self.autoruns_parser)
                tabs.addTab(self.autoruns_tab, "持久化检测")
            print("UI initialized")

    def main():
        print("Checking admin rights...")
        # 检查管理员权限
        if not is_admin():
            print("Not running as admin, trying to elevate...")
            # 尝试提权重启
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit(0)
        
        print("Creating QApplication...")
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # 使用Fusion风格
        
        print("Creating main window...")
        window = MainWindow()
        print("Showing main window...")
        window.show()
        
        print("Starting event loop...")
        sys.exit(app.exec())

    if __name__ == "__main__":
        main()
        
except Exception as e:
    print("Error occurred:")
    print(traceback.format_exc())
    input("Press Enter to exit...")  # 保持窗口打开以便查看错误