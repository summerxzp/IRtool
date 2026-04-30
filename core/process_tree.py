import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import psutil

logger = logging.getLogger('IRtool')

_SUSPICIOUS_PATH_FRAGMENTS = (
    '\\temp\\', '\\tmp\\',
    '\\appdata\\roaming\\',
    '\\appdata\\local\\temp\\',
    '\\downloads\\',
    '\\desktop\\',
    '\\public\\',
    '\\recycle',
)

_SYSTEM_PROC_EXPECTED_DIRS: dict = {
    'svchost.exe': ('\\system32\\', '\\syswow64\\'),
    'lsass.exe':   ('\\system32\\',),
    'csrss.exe':   ('\\system32\\',),
    'winlogon.exe':('\\system32\\',),
    'services.exe':('\\system32\\',),
    'smss.exe':    ('\\system32\\',),
    'wininit.exe': ('\\system32\\',),
    'spoolsv.exe': ('\\system32\\',),
}


def _check_suspicious(name: str, exe: str) -> Tuple[bool, str]:
    if not exe:
        return False, ''
    exe_lower = exe.lower()
    name_lower = name.lower()
    expected = _SYSTEM_PROC_EXPECTED_DIRS.get(name_lower)
    if expected and not any(d in exe_lower for d in expected):
        return True, '系统进程位于非标准路径'
    for frag in _SUSPICIOUS_PATH_FRAGMENTS:
        if frag in exe_lower:
            return True, '运行于用户可写目录'
    return False, ''


@dataclass
class ProcessNode:
    pid: int
    name: str
    exe: str
    cmdline: str
    create_time: str
    is_target: bool = False
    is_suspicious: bool = False
    suspicious_reason: str = ''


def _make_node(proc: psutil.Process, is_target: bool = False) -> Optional[ProcessNode]:
    try:
        with proc.oneshot():
            name = proc.name()
            try:
                exe = proc.exe()
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                exe = ''
            try:
                parts = proc.cmdline()
                cmdline = ' '.join(parts) if parts else ''
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                cmdline = ''
            try:
                ct = datetime.fromtimestamp(proc.create_time()).strftime('%H:%M:%S')
            except Exception:
                ct = ''
            is_suspicious, reason = _check_suspicious(name, exe)
            return ProcessNode(
                pid=proc.pid,
                name=name,
                exe=exe,
                cmdline=cmdline,
                create_time=ct,
                is_target=is_target,
                is_suspicious=is_suspicious,
                suspicious_reason=reason,
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_process_chain(pid: int) -> List[ProcessNode]:
    """返回 [目标进程, 父进程, 祖父进程, ...] 直到根进程。"""
    chain: List[ProcessNode] = []
    try:
        proc = psutil.Process(pid)
        node = _make_node(proc, is_target=True)
        if node:
            chain.append(node)
        for parent in proc.parents():
            node = _make_node(parent)
            if node:
                chain.append(node)
            if parent.pid in (0, 4):
                break
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        logger.warning(f'[ProcessTree] 获取进程链失败 pid={pid}: {e}')
    return chain
