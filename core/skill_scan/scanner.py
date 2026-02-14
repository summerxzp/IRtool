import fnmatch
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from .models import SkillFileEntry, SkillScanConfig, SkillScanResult


# 仅保留高价值 Skill 工具链路径；不扫描 AppData/Temp 全域目录。
BUILTIN_PATH_DEFINITIONS: Dict[str, Tuple[str, str]] = {
    "claude_home": ("Claude", r"%USERPROFILE%\\.claude"),
    "openclaw_home": ("OpenClaw", r"%USERPROFILE%\\.openclaw"),
    "codex_home": ("Codex", r"%USERPROFILE%\\.codex"),
    "claude_config": ("ClaudeConfig", r"%USERPROFILE%\\.config\\claude"),
    "openclaw_config": ("OpenClawConfig", r"%USERPROFILE%\\.config\\openclaw"),
}

DEFAULT_KNOWN_SKILL_FILES: Set[str] = {
    "skill.md",
    "skill.yaml",
    "skill.yml",
    "skill.json",
    "manifest.json",
    "mcpservers.json",
    "skills.json",
    "readme.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
}

SUSPICIOUS_EXTENSIONS: Set[str] = {
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

SUSPICIOUS_NAME_KEYWORDS: Tuple[str, ...] = (
    "loader",
    "dropper",
    "payload",
    "backdoor",
    "mimikatz",
    "stealer",
    "inject",
    "shellcode",
)

SKIP_DIR_NAMES: Set[str] = {
    ".git",
    ".hg",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".cache",
}


@dataclass(frozen=True)
class _ScanRoot:
    path: str
    source_type: str
    path_category: str


class SkillScanScanner:
    """Skill Scan 扫描器：聚焦工具链路径上的结构化发现。"""

    def scan(self, config: SkillScanConfig) -> SkillScanResult:
        roots = self._build_scan_roots(config)
        filters = self._normalize_filters(config.filename_filters)
        known_files = self._normalize_text_set(config.known_skill_files) or set(DEFAULT_KNOWN_SKILL_FILES)
        malicious_hashes = self._normalize_hash_set(config.malicious_hashes)

        entries: List[SkillFileEntry] = []
        errors: List[str] = []
        scanned_files = 0

        for root in roots:
            for file_path in self._iter_files(root.path, recursive=config.recursive):
                scanned_files += 1
                file_name = os.path.basename(file_path)
                if not self._matches_filename_filters(file_name, filters):
                    continue
                entry = self._build_entry(
                    file_path=file_path,
                    source_type=root.source_type,
                    path_category=root.path_category,
                    known_files=known_files,
                    malicious_hashes=malicious_hashes,
                )
                if entry:
                    entries.append(entry)
                else:
                    errors.append(f"build_entry_failed:{file_path}")

        suspicious_files = sum(1 for item in entries if item.is_malicious_hash or bool(item.risk_flags))
        return SkillScanResult(
            entries=entries,
            scan_time=datetime.now(),
            total_files=len(entries),
            scanned_files=scanned_files,
            suspicious_files=suspicious_files,
            errors=errors,
        )

    def _build_scan_roots(self, config: SkillScanConfig) -> List[_ScanRoot]:
        roots: List[_ScanRoot] = []
        seen = set()

        for key in config.builtin_paths:
            key_norm = (key or "").strip().lower()
            if key_norm not in BUILTIN_PATH_DEFINITIONS:
                continue
            category, path_expr = BUILTIN_PATH_DEFINITIONS[key_norm]
            root = self._normalize_path(path_expr)
            if not root or not os.path.isdir(root):
                continue
            dedup_key = root.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            roots.append(_ScanRoot(path=root, source_type="builtin", path_category=category))

        for custom in config.custom_paths:
            root = self._normalize_path(custom)
            if not root or not os.path.isdir(root):
                continue
            dedup_key = root.lower()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            roots.append(_ScanRoot(path=root, source_type="custom", path_category="Custom"))

        return roots

    @staticmethod
    def _normalize_path(path_value: str) -> str:
        if not path_value:
            return ""
        expanded = os.path.expandvars(os.path.expanduser(path_value.strip()))
        if not expanded:
            return ""
        return os.path.normpath(expanded)

    @staticmethod
    def _normalize_filters(raw_filters: Iterable[str]) -> List[str]:
        values = []
        for item in raw_filters:
            text = (item or "").strip().lower()
            if text:
                values.append(text)
        return values

    @staticmethod
    def _normalize_text_set(values: Iterable[str]) -> Set[str]:
        result: Set[str] = set()
        for value in values:
            text = (value or "").strip().lower()
            if text:
                result.add(text)
        return result

    @staticmethod
    def _normalize_hash_set(values: Iterable[str]) -> Set[str]:
        result: Set[str] = set()
        for value in values:
            text = (value or "").strip().lower()
            if len(text) == 64 and all(c in "0123456789abcdef" for c in text):
                result.add(text)
        return result

    @staticmethod
    def _matches_filename_filters(file_name: str, filters: List[str]) -> bool:
        if not filters:
            return True
        text = (file_name or "").strip().lower()
        if not text:
            return False
        for pattern in filters:
            if any(ch in pattern for ch in "*?[]"):
                if fnmatch.fnmatch(text, pattern):
                    return True
            elif text == pattern:
                return True
        return False

    def _iter_files(self, root_path: str, recursive: bool) -> Iterable[str]:
        if recursive:
            for current_root, dir_names, file_names in os.walk(root_path, topdown=True, followlinks=False):
                dir_names[:] = [
                    name
                    for name in dir_names
                    if name.lower() not in SKIP_DIR_NAMES and not os.path.islink(os.path.join(current_root, name))
                ]
                for name in file_names:
                    file_path = os.path.join(current_root, name)
                    if os.path.islink(file_path):
                        continue
                    if os.path.isfile(file_path):
                        yield file_path
            return

        try:
            for name in os.listdir(root_path):
                file_path = os.path.join(root_path, name)
                if os.path.islink(file_path):
                    continue
                if os.path.isfile(file_path):
                    yield file_path
        except Exception:
            return

    def _build_entry(
        self,
        file_path: str,
        source_type: str,
        path_category: str,
        known_files: Set[str],
        malicious_hashes: Set[str],
    ):
        try:
            stat = os.stat(file_path)
        except Exception:
            return None

        file_name = Path(file_path).name
        sha256_value = ""
        tags: List[str] = []
        risk_flags: List[str] = []
        matched_rules: List[str] = []

        try:
            sha256_value = self._hash_file(file_path)
        except Exception:
            tags.append("hash_error")

        file_name_lower = file_name.lower()
        is_known_skill_file = self._is_known_skill_file(file_path, file_name_lower, known_files)
        is_malicious_hash = bool(sha256_value and sha256_value in malicious_hashes)

        ext = Path(file_path).suffix.lower()
        if ext in SUSPICIOUS_EXTENSIONS:
            risk_flags.append(f"high_risk_extension:{ext}")
            matched_rules.append("R_EXT_HIGH_RISK: 高风险扩展名")
        for keyword in SUSPICIOUS_NAME_KEYWORDS:
            if keyword in file_name_lower:
                risk_flags.append(f"name_keyword:{keyword}")
                matched_rules.append(f"R_NAME_KEYWORD: 文件名包含 {keyword}")

        if is_known_skill_file:
            tags.append("known_skill_file")
        if is_malicious_hash:
            tags.append("malicious_hash_hit")
            risk_flags.append("hash_in_malicious_set")
            matched_rules.append("R_HASH_BLOCKLIST: 命中恶意 Hash 清单")

        if not is_known_skill_file and self._path_looks_like_skill_dir(file_path):
            risk_flags.append("unknown_file_in_skill_path")
            matched_rules.append("R_UNKNOWN_IN_SKILL: Skill 路径出现未知文件")

        return SkillFileEntry(
            file_name=file_name,
            full_path=file_path,
            size=int(stat.st_size),
            mtime=datetime.fromtimestamp(stat.st_mtime),
            sha256=sha256_value,
            source_type=source_type,
            path_category=path_category,
            is_known_skill_file=is_known_skill_file,
            is_malicious_hash=is_malicious_hash,
            matched_rules=matched_rules,
            risk_flags=risk_flags,
            tags=tags,
        )

    @staticmethod
    def _is_known_skill_file(file_path: str, file_name_lower: str, known_files: Set[str]) -> bool:
        if file_name_lower in known_files:
            return True
        if file_name_lower.endswith(".skill"):
            return True

        normalized = file_path.replace("\\", "/").lower()
        if "/skills/" in normalized:
            if Path(file_path).suffix.lower() in {".md", ".json", ".yaml", ".yml", ".toml", ".txt"}:
                return True
        return False

    @staticmethod
    def _path_looks_like_skill_dir(file_path: str) -> bool:
        normalized = file_path.replace("\\", "/").lower()
        return any(marker in normalized for marker in ("/.claude", "/.openclaw", "/.codex", "/skills/"))

    @staticmethod
    def _hash_file(file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
