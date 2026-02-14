from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class SkillFileEntry:
    file_name: str
    full_path: str
    size: int
    mtime: datetime
    sha256: str
    source_type: str
    path_category: str
    is_known_skill_file: bool = False
    is_malicious_hash: bool = False
    matched_rules: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class SkillScanConfig:
    builtin_paths: List[str] = field(default_factory=list)
    custom_paths: List[str] = field(default_factory=list)
    filename_filters: List[str] = field(default_factory=list)
    known_skill_files: List[str] = field(default_factory=list)
    malicious_hashes: List[str] = field(default_factory=list)
    recursive: bool = True


@dataclass
class SkillScanResult:
    entries: List[SkillFileEntry] = field(default_factory=list)
    scan_time: datetime = field(default_factory=datetime.now)
    total_files: int = 0
    scanned_files: int = 0
    suspicious_files: int = 0
    errors: List[str] = field(default_factory=list)
