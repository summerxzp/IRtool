from dataclasses import dataclass, field
from typing import List


@dataclass
class SkillAuditFinding:
    """单个可疑 skill 文件记录。"""

    root_name: str
    root_path: str
    file_path: str
    relative_path: str
    extension: str
    size_bytes: int
    modified_at: str
    sha256: str = ""
    risk_level: str = "low"
    reasons: List[str] = field(default_factory=list)
    indicators: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class SkillAuditReport:
    """skill 路径体检结果。"""

    generated_at: str
    roots_scanned: List[str]
    files_scanned: int
    findings: List[SkillAuditFinding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def suspicious_count(self) -> int:
        return len(self.findings)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "roots_scanned": self.roots_scanned,
            "files_scanned": self.files_scanned,
            "suspicious_count": self.suspicious_count,
            "errors": list(self.errors),
            "findings": [f.__dict__ for f in self.findings],
        }
