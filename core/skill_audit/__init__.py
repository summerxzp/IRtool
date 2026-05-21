"""
[DEPRECATED] skill_audit 模块已废弃，功能已迁移至 skill_scan 模块。
如需使用，请直接 import core.skill_audit，但不再从 core 包级别导出。
"""
import warnings

warnings.warn(
    "core.skill_audit is deprecated, use core.skill_scan instead",
    DeprecationWarning,
    stacklevel=2,
)

from .models import SkillAuditFinding, SkillAuditReport
from .scanner import SkillAuditOptions, SkillAuditScanner, DEFAULT_SKILL_ROOTS

__all__ = [
    "SkillAuditFinding",
    "SkillAuditReport",
    "SkillAuditOptions",
    "SkillAuditScanner",
    "DEFAULT_SKILL_ROOTS",
]
