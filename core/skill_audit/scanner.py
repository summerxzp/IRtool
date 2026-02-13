import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .models import SkillAuditFinding, SkillAuditReport


DEFAULT_SKILL_ROOTS: Tuple[Tuple[str, str], ...] = (
    ("openclaw_user", r"%USERPROFILE%\.openclaw\skills"),
    ("openclaw_appdata", r"%APPDATA%\OpenClaw\skills"),
    ("openclaw_localappdata", r"%LOCALAPPDATA%\OpenClaw\skills"),
    ("claudecode_user", r"%USERPROFILE%\.claude\skills"),
    ("claudecode_appdata", r"%APPDATA%\ClaudeCode\skills"),
    ("codex_user", r"%USERPROFILE%\.codex\skills"),
)


@dataclass
class SkillAuditOptions:
    compute_hash: bool = True
    only_suspicious: bool = True
    max_files_per_root: int = 10000
    max_text_bytes: int = 512 * 1024
    include_extensions: Tuple[str, ...] = ()
    skip_extensions: Tuple[str, ...] = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
    )


class SkillAuditScanner:
    """常见 Agent skill 路径体检扫描器。"""

    HIGH_RISK_EXTENSIONS = {
        ".exe",
        ".dll",
        ".sys",
        ".bat",
        ".cmd",
        ".ps1",
        ".vbs",
        ".js",
        ".jar",
        ".hta",
        ".scr",
    }
    SCRIPT_EXTENSIONS = {".py", ".ps1", ".bat", ".cmd", ".js", ".vbs", ".sh", ".psm1"}
    SUSPICIOUS_NAME_KEYWORDS = {
        "payload",
        "backdoor",
        "stealer",
        "loader",
        "dropper",
        "inject",
        "mimikatz",
        "ransom",
        "cobalt",
    }
    SUSPICIOUS_CONTENT_PATTERNS = (
        "invoke-webrequest",
        "downloadstring(",
        "frombase64string(",
        "powershell -enc",
        "certutil -urlcache",
        "bitsadmin /transfer",
        "rundll32",
        "regsvr32",
        "mshta",
        "curl ",
        "wget ",
        "http://",
        "https://",
    )

    def __init__(self, options: SkillAuditOptions = None):
        self.options = options or SkillAuditOptions()

    def scan_common_roots(self) -> SkillAuditReport:
        return self.scan_roots(DEFAULT_SKILL_ROOTS)

    def scan_roots(self, roots: Iterable[Tuple[str, str]]) -> SkillAuditReport:
        now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        report = SkillAuditReport(generated_at=now, roots_scanned=[], files_scanned=0)

        for root_name, root_expr in roots:
            root_path = self._expand_path(root_expr)
            if not root_path:
                continue
            report.roots_scanned.append(f"{root_name}:{root_path}")

            if not os.path.exists(root_path):
                continue
            if not os.path.isdir(root_path):
                report.errors.append(f"{root_name} not a directory: {root_path}")
                continue

            scanned_count = 0
            for file_path in Path(root_path).rglob("*"):
                if scanned_count >= self.options.max_files_per_root:
                    report.errors.append(
                        f"{root_name} reached max_files_per_root={self.options.max_files_per_root}"
                    )
                    break
                if not file_path.is_file():
                    continue
                scanned_count += 1
                report.files_scanned += 1

                ext = file_path.suffix.lower()
                if self.options.include_extensions and ext not in self.options.include_extensions:
                    continue
                if ext in self.options.skip_extensions:
                    continue

                try:
                    finding = self._build_finding(root_name, root_path, file_path)
                except Exception as exc:
                    report.errors.append(f"{file_path}: {exc}")
                    continue

                if self.options.only_suspicious and finding.risk_level == "low":
                    continue
                report.findings.append(finding)

        report.findings.sort(key=self._finding_sort_key, reverse=True)
        return report

    def _build_finding(self, root_name: str, root_path: str, file_path: Path) -> SkillAuditFinding:
        stat = file_path.stat()
        modified = datetime.utcfromtimestamp(stat.st_mtime).replace(microsecond=0).isoformat() + "Z"
        relative_path = str(file_path.relative_to(root_path))
        ext = file_path.suffix.lower()

        reasons: List[str] = []
        indicators: List[str] = []
        score = 0

        if ext in self.HIGH_RISK_EXTENSIONS:
            reasons.append(f"high_risk_extension:{ext}")
            score += 3
        elif ext in self.SCRIPT_EXTENSIONS:
            reasons.append(f"script_extension:{ext}")
            score += 1

        lower_name = file_path.name.lower()
        for keyword in self.SUSPICIOUS_NAME_KEYWORDS:
            if keyword in lower_name:
                indicators.append(f"name_keyword:{keyword}")
                score += 2

        if stat.st_size >= 20 * 1024 * 1024:
            reasons.append("unusual_large_file")
            score += 1

        content_indicators = self._scan_content_indicators(file_path, ext, stat.st_size)
        if content_indicators:
            indicators.extend(content_indicators)
            score += min(4, len(content_indicators))
            reasons.append("suspicious_content_pattern")

        sha256_value = self._hash_file(file_path) if self.options.compute_hash else ""

        risk_level = "low"
        if score >= 6:
            risk_level = "high"
        elif score >= 3:
            risk_level = "medium"

        return SkillAuditFinding(
            root_name=root_name,
            root_path=root_path,
            file_path=str(file_path),
            relative_path=relative_path,
            extension=ext,
            size_bytes=stat.st_size,
            modified_at=modified,
            sha256=sha256_value,
            risk_level=risk_level,
            reasons=reasons,
            indicators=indicators[:10],
        )

    def _scan_content_indicators(self, file_path: Path, ext: str, size_bytes: int) -> List[str]:
        if size_bytes > self.options.max_text_bytes:
            return []
        # 粗略判定文本扩展，避免对二进制做无意义解码。
        if ext and ext not in self.SCRIPT_EXTENSIONS and ext not in {
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".txt",
            ".md",
            ".ini",
        }:
            return []

        try:
            raw = file_path.read_bytes()
        except Exception:
            return []

        text = self._decode_text_best_effort(raw).lower()
        indicators = []
        for pattern in self.SUSPICIOUS_CONTENT_PATTERNS:
            if pattern in text:
                indicators.append(f"content_pattern:{pattern}")
        return indicators

    @staticmethod
    def _decode_text_best_effort(raw: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk", "cp936", "latin-1"):
            try:
                return raw.decode(encoding, errors="strict")
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _hash_file(file_path: Path) -> str:
        h = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _expand_path(path_expr: str) -> str:
        if not path_expr:
            return ""
        expanded = os.path.expandvars(path_expr)
        expanded = os.path.expanduser(expanded)
        return os.path.normpath(expanded)

    @staticmethod
    def _finding_sort_key(finding: SkillAuditFinding):
        risk_order = {"high": 3, "medium": 2, "low": 1}
        return (
            risk_order.get(finding.risk_level, 0),
            len(finding.indicators),
            len(finding.reasons),
            finding.modified_at,
        )
