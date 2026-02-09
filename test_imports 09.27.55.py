#!/usr/bin/env python3
# test_imports.py - Test script to check imports
import sys
import traceback
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

print("Testing imports...")

try:
    print("1. Testing basic imports...")
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
    from PyQt6.QtCore import Qt
    print("   Basic imports successful")
    
    print("2. Testing core imports...")
    from core.network_monitor import NetworkMonitor
    print("   NetworkMonitor import successful")
    
    from core.autoruns_parser import AutorunsParser
    print("   AutorunsParser import successful")
    

    
    print("3. Testing UI imports...")
    from ui.network_tab import NetworkTab
    print("   NetworkTab import successful")
    
    from ui.autoruns_tab import AutorunsTab
    print("   AutorunsTab import successful")
    
    print("\nAll imports successful!")
    
except Exception as e:
    print(f"\nImport error: {e}")
    print("\nTraceback:")
    traceback.print_exc()
    input("Press Enter to exit...")
