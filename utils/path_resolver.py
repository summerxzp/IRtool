from PyQt6.QtWidgets import QFileDialog, QWidget
from PyQt6.QtCore import QObject, pyqtSignal
import os
from typing import Optional, Literal
from enum import Enum


class PathScope(Enum):
    """路径作用域枚举"""
    SELF = "self"
    DIRECTORY = "directory"
    PARENT = "parent"


class PathResolver(QObject):
    """路径解析器 - 统一解析 self / directory / parent"""
    
    @staticmethod
    def resolve(image_path: str, scope: PathScope) -> Optional[str]:
        """
        解析路径
        
        Args:
            image_path: 原始路径
            scope: 路径作用域
            
        Returns:
            解析后的路径，失败返回 None
        """
        try:
            if not image_path:
                return None
            
            if scope == PathScope.SELF:
                return image_path
            elif scope == PathScope.DIRECTORY:
                return os.path.dirname(image_path)
            elif scope == PathScope.PARENT:
                return os.path.dirname(os.path.dirname(image_path))
            
            return None
        except Exception:
            return None
    
    @staticmethod
    def select_directory(parent: QWidget, title: str = "选择目录") -> Optional[str]:
        """
        选择目录
        
        Args:
            parent: 父窗口
            title: 对话框标题
            
        Returns:
            选择的目录路径，取消返回 None
        """
        try:
            path = QFileDialog.getExistingDirectory(parent, title)
            return path if path else None
        except Exception:
            return None
    
    @staticmethod
    def select_file(parent: QWidget, title: str = "选择文件", 
                  filter: str = "所有文件 (*.*)") -> Optional[str]:
        """
        选择文件
        
        Args:
            parent: 父窗口
            title: 对话框标题
            filter: 文件过滤器
            
        Returns:
            选择的文件路径，取消返回 None
        """
        try:
            path, _ = QFileDialog.getOpenFileName(parent, title, "", filter)
            return path if path else None
        except Exception:
            return None
    
    @staticmethod
    def save_file(parent: QWidget, title: str = "保存文件",
                 default_name: str = "", filter: str = "所有文件 (*.*)") -> Optional[str]:
        """
        保存文件
        
        Args:
            parent: 父窗口
            title: 对话框标题
            default_name: 默认文件名
            filter: 文件过滤器
            
        Returns:
            保存的文件路径，取消返回 None
        """
        try:
            path, _ = QFileDialog.getSaveFileName(parent, title, default_name, filter)
            return path if path else None
        except Exception:
            return None
