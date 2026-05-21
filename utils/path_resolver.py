"""
路径解析工具 - 统一获取应用根目录和其他路径
"""
from pathlib import Path
from enum import Enum
import sys
import os


class PathScope(Enum):
    """路径解析范围"""
    SELF = "self"
    DIRECTORY = "directory"
    PARENT = "parent"


class PathResolver:
    """路径解析工具类"""

    @staticmethod
    def get_app_dir() -> Path:
        """获取应用根目录（支持源码运行和PyInstaller打包）"""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        else:
            return Path(__file__).parent.parent

    @staticmethod
    def get_data_dir() -> Path:
        """获取数据目录"""
        base_dir = PathResolver.get_app_dir()
        possible_paths = [
            base_dir / "data",
            base_dir / "_internal" / "data",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[0]

    @staticmethod
    def get_rules_path() -> Path:
        """获取规则文件路径"""
        return PathResolver.get_data_dir() / "rules.json"

    @staticmethod
    def get_tools_dir() -> Path:
        """获取工具目录"""
        base_dir = PathResolver.get_app_dir()
        possible_paths = [
            base_dir / "tools",
            base_dir / "_internal" / "tools",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return possible_paths[0]

    @staticmethod
    def resolve(image_path: str, scope: PathScope) -> str:
        """根据作用域解析目标路径"""
        if not image_path or not os.path.exists(image_path):
            return image_path

        path = Path(image_path)
        if scope == PathScope.SELF:
            return image_path
        elif scope == PathScope.DIRECTORY:
            if path.is_file():
                return str(path.parent)
            return image_path
        elif scope == PathScope.PARENT:
            if path.is_file():
                return str(path.parent.parent) if path.parent.parent.exists() else str(path.parent)
            return str(path.parent) if path.parent.exists() else image_path
        return image_path

    @staticmethod
    def select_directory(parent, title: str = "选择目录") -> str:
        """选择目录对话框"""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(parent, title)
        return folder if folder else ""

    @staticmethod
    def save_file(parent, title: str, default_name: str, file_filter: str) -> str:
        """保存文件对话框"""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            parent, title, default_name, file_filter
        )
        return path


def get_app_dir() -> Path:
    """获取应用根目录（支持源码运行和PyInstaller打包）"""
    return PathResolver.get_app_dir()


def get_data_dir() -> Path:
    """获取数据目录"""
    return PathResolver.get_data_dir()


def get_rules_path() -> Path:
    """获取规则文件路径"""
    return PathResolver.get_rules_path()


def get_tools_dir() -> Path:
    """获取工具目录"""
    return PathResolver.get_tools_dir()
