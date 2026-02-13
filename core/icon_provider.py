# core/icon_provider.py
"""
图标提供者模块 - 负责从可执行文件提取图标并缓存

设计原则:
1. 使用 Qt 自带机制，不引入第三方依赖
2. 按 image_path 做 key 缓存，同一路径只提取一次
3. 缓存生命周期 >= 当前会话
4. 不阻塞 UI，提取失败时使用默认占位图标
"""

import os
import sys
from typing import Optional, Dict
from PyQt6.QtCore import Qt, QSize, QFileInfo
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import QFileIconProvider


class IconProvider:
    """图标提供者 - 单例模式"""
    
    _instance: Optional['IconProvider'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'IconProvider':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if IconProvider._initialized:
            return
        
        self._icon_cache: Dict[str, QIcon] = {}
        self._file_icon_provider = QFileIconProvider()
        self._default_icon: Optional[QIcon] = None
        self._icon_size = QSize(16, 16)
        
        IconProvider._initialized = True
    
    def _get_default_icon(self) -> QIcon:
        """获取默认占位图标（懒加载）"""
        if self._default_icon is None:
            # 创建一个简单的灰色方块作为默认图标
            pixmap = QPixmap(self._icon_size)
            pixmap.fill(QColor(200, 200, 200))
            self._default_icon = QIcon(pixmap)
        return self._default_icon
    
    def _normalize_path(self, path: str) -> str:
        """标准化路径作为缓存 key"""
        if not path:
            return ""
        # 统一大小写，去除首尾空格
        return path.strip().lower()
    
    def _extract_windows_icon(self, image_path: str) -> Optional[QIcon]:
        """
        从 Windows 可执行文件提取图标
        使用 QFileIconProvider 加载文件图标
        """
        try:
            # 使用 QFileIconProvider 获取图标
            file_info = QFileInfo(image_path)
            icon = self._file_icon_provider.icon(file_info)
            
            if not icon.isNull():
                # 验证图标是否有效（获取一个尺寸的pixmap）
                pixmap = icon.pixmap(self._icon_size)
                if not pixmap.isNull() and not pixmap.size().isEmpty():
                    return icon
        except Exception:
            pass
        
        return None
    
    def get_icon(self, image_path: str) -> QIcon:
        """
        获取指定路径的图标
        
        Args:
            image_path: 可执行文件路径
            
        Returns:
            QIcon: 提取的图标或默认占位图标
        """
        if not image_path or image_path.lower() == 'file not found':
            return self._get_default_icon()
        
        # 检查缓存
        cache_key = self._normalize_path(image_path)
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        # 检查文件是否存在
        if not os.path.exists(image_path):
            # 文件不存在，使用默认图标并缓存
            self._icon_cache[cache_key] = self._get_default_icon()
            return self._icon_cache[cache_key]
        
        try:
            # 尝试提取图标
            icon = self._extract_windows_icon(image_path)
            
            if icon is None:
                icon = self._get_default_icon()
            
            # 缓存结果
            self._icon_cache[cache_key] = icon
            return icon
            
        except Exception as e:
            # 任何异常都返回默认图标并缓存
            self._icon_cache[cache_key] = self._get_default_icon()
            return self._icon_cache[cache_key]
    
    def get_icon_with_overlay(self, image_path: str, risk_level: int) -> QIcon:
        """
        获取带风险标记的图标
        
        Args:
            image_path: 可执行文件路径
            risk_level: 风险等级 (0=正常, 1=可疑, 2=高风险)
            
        Returns:
            QIcon: 带标记的图标
        """
        base_icon = self.get_icon(image_path)
        
        if risk_level == 0:
            return base_icon
        
        # 创建带标记的图标
        pixmap = base_icon.pixmap(self._icon_size)
        if pixmap.isNull():
            pixmap = QPixmap(self._icon_size)
            pixmap.fill(QColor(200, 200, 200))
        
        # 在右下角绘制风险标记
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if risk_level == 2:  # 高风险 - 红色圆点
            painter.setBrush(QColor(255, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(10, 10, 6, 6)
        elif risk_level == 1:  # 可疑 - 黄色圆点
            painter.setBrush(QColor(255, 200, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(10, 10, 6, 6)
        
        painter.end()
        
        return QIcon(pixmap)
    
    def clear_cache(self):
        """清除图标缓存"""
        self._icon_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            'cached_count': len(self._icon_cache),
            'cache_size': len(self._icon_cache) * self._icon_size.width() * self._icon_size.height() * 4
        }


# 全局访问点
def get_icon_provider() -> IconProvider:
    """获取 IconProvider 单例实例"""
    return IconProvider()


def get_icon(image_path: str) -> QIcon:
    """
    快捷函数：获取指定路径的图标
    
    Args:
        image_path: 可执行文件路径
        
    Returns:
        QIcon: 提取的图标或默认占位图标
    """
    return get_icon_provider().get_icon(image_path)
