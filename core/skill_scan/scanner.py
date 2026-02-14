import fnmatch
import glob
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .models import SkillFileEntry, SkillScanConfig, SkillScanResult


BUILTIN_PATH_DEFINITIONS: Dict[str, Tuple[str, str]] = {
    "appdata": ("AppData", r"%APPDATA%"),
    "localappdata": ("LocalAppData", r"%LOCALAPPDATA%"),
    "programdata": ("ProgramData", r"%PROGRAMDATA%"),
    "temp": ("Temp", r"%TEMP%"),
    "downloads": ("Downloads", r"C:\\Users\\*\\Downloads"),
}


@dataclass(frozen=True)
class _ScanRoot:
    path: str
    source_type: str
    path_category: str


class SkillScanScanner:
    """独立 Skill Scan 扫描器：仅负责文件发现与 hash 归集。"""

    def scan(self, config: SkillScanConfig) -> SkillScanResult:
        roots = self._build_scan_roots(config)
        filters = self._normalize_filters(config.filename_filters)

        entries: List[SkillFileEntry] = []
        for root in roots:
            for file_path in self._iter_files(root.path, recursive=config.recursive):
                file_name = os.path.basename(file_path)
                if not self._matches_filename_filters(file_name, filters):
                    continue
                entry = self._build_entry(file_path, root.source_type, root.path_category)
                if entry:
                    entries.append(entry)

        return SkillScanResult(
            entries=entries,
            scan_time=datetime.now(),
            total_files=len(entries),
        )

    def _build_scan_roots(self, config: SkillScanConfig) -> List[_ScanRoot]:
        roots: List[_ScanRoot] = []
        seen = set()

        for key in config.builtin_paths:
            key_norm = (key or "").strip().lower()
            if key_norm not in BUILTIN_PATH_DEFINITIONS:
                continue
            category, pattern = BUILTIN_PATH_DEFINITIONS[key_norm]
            for resolved in self._expand_path_pattern(pattern):
                root = self._normalize_path(resolved)
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
    def _expand_path_pattern(path_pattern: str) -> List[str]:
        if not path_pattern:
            return []
        expanded = os.path.expandvars(os.path.expanduser(path_pattern))
        if any(ch in expanded for ch in "*?[]"):
            return [p for p in glob.glob(expanded) if os.path.isdir(p)]
        return [expanded]

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
        filters: List[str] = []
        for item in raw_filters:
            value = (item or "").strip().lower()
            if value:
                filters.append(value)
        return filters

    @staticmethod
    def _matches_filename_filters(file_name: str, filters: List[str]) -> bool:
        if not filters:
            return True
        name = (file_name or "").strip().lower()
        if not name:
            return False
        for pattern in filters:
            if any(ch in pattern for ch in "*?[]"):
                if fnmatch.fnmatch(name, pattern):
                    return True
            elif name == pattern:
                return True
        return False

    def _iter_files(self, root_path: str, recursive: bool) -> Iterable[str]:
        if recursive:
            for current_root, dir_names, file_names in os.walk(root_path, topdown=True, followlinks=False):
                dir_names[:] = [
                    name for name in dir_names if not os.path.islink(os.path.join(current_root, name))
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

    def _build_entry(self, file_path: str, source_type: str, path_category: str):
        try:
            stat = os.stat(file_path)
        except Exception:
            return None

        sha256_value = ""
        tags: List[str] = []
        try:
            sha256_value = self._hash_file(file_path)
        except Exception:
            tags.append("hash_error")

        return SkillFileEntry(
            file_name=Path(file_path).name,
            full_path=file_path,
            size=int(stat.st_size),
            mtime=datetime.fromtimestamp(stat.st_mtime),
            sha256=sha256_value,
            source_type=source_type,
            path_category=path_category,
            tags=tags,
        )

    @staticmethod
    def _hash_file(file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
