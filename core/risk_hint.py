# core/risk_hint.py
"""
风险提示模块 - 轻量级风险标注逻辑

设计原则:
1. 这是"辅助分析信号"，不是最终判定
2. 不引入复杂评分模型
3. 基于【图标 + 路径 + 签名】的联合判定
4. 所有高亮逻辑必须可被关闭（配置项）

风险等级定义:
- SAFE (0): 明显可信，无需提示
- SUSPICIOUS (1): 可疑，UI 上弱提示
- HIGH_RISK (2): 高风险，UI 上强提示/高亮行
"""

import os
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path


class RiskLevel(IntEnum):
    """风险等级枚举"""
    SAFE = 0          # 明显可信
    SUSPICIOUS = 1    # 可疑（弱提示）
    HIGH_RISK = 2     # 高风险（强提示）


@dataclass
class RiskHint:
    """风险提示数据类"""
    level: RiskLevel
    reasons: List[str]  # 风险原因列表（用于调试/日志）
    
    def is_risky(self) -> bool:
        """是否有风险"""
        return self.level > RiskLevel.SAFE
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        names = {
            RiskLevel.SAFE: "正常",
            RiskLevel.SUSPICIOUS: "可疑",
            RiskLevel.HIGH_RISK: "高风险"
        }
        return names.get(self.level, "未知")


class RiskEvaluator:
    """风险评估器 - 单例模式"""
    
    _instance: Optional['RiskEvaluator'] = None
    _initialized: bool = False
    
    # 可配置项（可通过配置文件或 UI 修改）
    ENABLE_RISK_HIGHLIGHT: bool = True  # 是否启用风险高亮
    
    # 系统可信目录列表
    TRUSTED_SYSTEM_PATHS: List[str] = [
        r"c:\windows\system32",
        r"c:\windows\syswow64",
        r"c:\program files",
        r"c:\program files (x86)",
    ]
    
    # 高风险目录列表（用户可写目录）
    HIGH_RISK_PATHS: List[str] = [
        "\\appdata\\",
        "\\temp\\",
        "\\tmp\\",
        "\\downloads\\",
        "\\desktop\\",
        "\\documents\\",
    ]
    
    # 可信发布者列表（部分匹配）
    TRUSTED_PUBLISHERS: List[str] = [
        "microsoft",
        "windows",
        "intel",
        "nvidia",
        "amd",
    ]
    
    def __new__(cls) -> 'RiskEvaluator':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if RiskEvaluator._initialized:
            return
        RiskEvaluator._initialized = True
    
    def _normalize_path(self, path: str) -> str:
        """标准化路径用于比较"""
        if not path:
            return ""
        return path.lower().strip()
    
    def _is_system_path(self, image_path: str) -> bool:
        """检查是否为系统可信目录"""
        if not image_path:
            return False
        
        path_lower = self._normalize_path(image_path)
        
        for trusted_path in self.TRUSTED_SYSTEM_PATHS:
            if path_lower.startswith(trusted_path.lower()):
                return True
        
        return False
    
    def _is_high_risk_path(self, image_path: str) -> bool:
        """检查是否为高风险目录"""
        if not image_path:
            return False
        
        path_lower = self._normalize_path(image_path)
        
        for risk_path in self.HIGH_RISK_PATHS:
            if risk_path in path_lower:
                return True
        
        return False
    
    def _is_trusted_publisher(self, publisher: str, signer: str) -> bool:
        """检查是否为可信发布者"""
        if not publisher and not signer:
            return False
        
        check_text = f"{publisher} {signer}".lower()
        
        for trusted in self.TRUSTED_PUBLISHERS:
            if trusted in check_text:
                return True
        
        return False
    
    def _is_verified_signature(self, signer_status: str) -> bool:
        """检查签名是否已验证"""
        if not signer_status:
            return False
        return '(verified)' in signer_status.lower()
    
    def _file_exists(self, image_path: str) -> bool:
        """检查文件是否存在"""
        if not image_path or image_path.lower() == 'file not found':
            return False
        return os.path.exists(image_path)
    
    def evaluate(self, entry_data: Dict[str, Any]) -> RiskHint:
        """
        评估条目风险等级
        
        Args:
            entry_data: 条目数据字典，应包含以下字段:
                - image_path: 文件路径
                - publisher: 发布者
                - signer_status: 签名状态
                - file_exists: 文件是否存在 (可选)
                
        Returns:
            RiskHint: 风险评估结果
        """
        if not self.ENABLE_RISK_HIGHLIGHT:
            return RiskHint(level=RiskLevel.SAFE, reasons=["风险高亮已禁用"])
        
        image_path = entry_data.get('image_path', '')
        publisher = entry_data.get('publisher', '')
        signer_status = entry_data.get('signer_status', '')
        file_exists = entry_data.get('file_exists', True)
        
        reasons = []
        
        # ========== 高风险判定 ==========
        
        # 1. 文件不存在
        if not file_exists:
            reasons.append("文件不存在")
        
        # 2. 无签名 + 非系统目录
        is_verified = self._is_verified_signature(signer_status)
        is_system_path = self._is_system_path(image_path)
        
        if not is_verified and not is_system_path:
            reasons.append("无有效签名且不在系统目录")
        
        # 3. 位于高风险目录（AppData/Temp等）
        if self._is_high_risk_path(image_path):
            reasons.append("位于用户可写目录")
        
        # 高风险判定：满足以下任一条件
        # - 文件不存在
        # - 无签名 + 非系统目录 + 位于高风险路径
        if not file_exists:
            return RiskHint(level=RiskLevel.HIGH_RISK, reasons=reasons)
        
        if not is_verified and not is_system_path and self._is_high_risk_path(image_path):
            return RiskHint(level=RiskLevel.HIGH_RISK, reasons=reasons)
        
        # ========== 可疑判定 ==========
        
        # 1. 有图标但非系统目录且发布者未知
        if not is_system_path and not self._is_trusted_publisher(publisher, signer_status):
            if not is_verified:
                reasons.append("非系统目录且发布者未知")
        
        # 2. 无签名但位于系统目录（可能是系统文件但签名验证失败）
        if not is_verified and is_system_path:
            reasons.append("系统目录文件但签名验证失败")
        
        # 可疑判定：满足以下任一条件
        # - 非系统目录 + 发布者未知 + 无签名
        # - 无签名但位于系统目录
        if reasons and not is_verified:
            return RiskHint(level=RiskLevel.SUSPICIOUS, reasons=reasons)
        
        # ========== 明显可信 ==========
        # - Microsoft 签名
        # - 位于 System32 / Program Files
        # - 图标正常且常见
        if is_verified and (is_system_path or self._is_trusted_publisher(publisher, signer_status)):
            return RiskHint(level=RiskLevel.SAFE, reasons=["已签名且位于可信位置"])
        
        # 默认：安全
        return RiskHint(level=RiskLevel.SAFE, reasons=["无明显风险特征"])
    
    def evaluate_from_entry(self, entry) -> RiskHint:
        """
        从 AutorunEntry 对象评估风险
        
        Args:
            entry: AutorunEntry 对象或具有相应属性的对象
            
        Returns:
            RiskHint: 风险评估结果
        """
        # 统一提取数据
        if hasattr(entry, 'to_dict'):
            data = entry.to_dict()
        elif hasattr(entry, '__dict__'):
            data = entry.__dict__
        else:
            data = dict(entry)
        
        return self.evaluate(data)


# 全局访问点
def get_risk_evaluator() -> RiskEvaluator:
    """获取 RiskEvaluator 单例实例"""
    return RiskEvaluator()


def evaluate(entry_data: Dict[str, Any]) -> RiskHint:
    """
    快捷函数：评估条目风险等级
    
    Args:
        entry_data: 条目数据字典
        
    Returns:
        RiskHint: 风险评估结果
    """
    return get_risk_evaluator().evaluate(entry_data)


def get_risk_color(risk_level: RiskLevel) -> Optional[str]:
    """
    获取风险等级对应的颜色（用于 UI）
    
    Args:
        risk_level: 风险等级
        
    Returns:
        str: 颜色代码或 None
    """
    colors = {
        RiskLevel.SAFE: None,           # 默认颜色
        RiskLevel.SUSPICIOUS: "#FFF8DC", # 浅黄色（Cornsilk）
        RiskLevel.HIGH_RISK: "#FFE4E1",  # 浅红色（MistyRose）
    }
    return colors.get(risk_level)


def get_risk_foreground_color(risk_level: RiskLevel) -> Optional[str]:
    """
    获取风险等级对应的前景颜色（字体颜色）
    
    Args:
        risk_level: 风险等级
        
    Returns:
        str: 颜色代码或 None
    """
    colors = {
        RiskLevel.SAFE: None,
        RiskLevel.SUSPICIOUS: "#B8860B",  # 深金色（DarkGoldenRod）
        RiskLevel.HIGH_RISK: "#8B0000",   # 深红色（DarkRed）
    }
    return colors.get(risk_level)
