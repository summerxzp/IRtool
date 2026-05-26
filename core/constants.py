# core/constants.py
"""全局常量定义"""

import os
import sys
from pathlib import Path


def _read_version_from_pyproject() -> str:
    if getattr(sys, 'frozen', False):
        env_ver = os.environ.get("IRTOOL_VERSION", "")
        if env_ver:
            return env_ver
        ver_file = Path(sys.executable).parent / ".version"
        if ver_file.exists():
            return ver_file.read_text(encoding="utf-8").strip()
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "0.0.0"


# 应用信息
APP_NAME = "终端安全检测工具"
APP_ID = "com.internal.IRtool"
APP_VERSION = _read_version_from_pyproject()
BUILD_TYPE = "release"
BUILD_DATE = "2026-05-27"

# 主窗口
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 700

# 线程池
MAX_THREAD_COUNT = 3

# 网络监控
NETWORK_REFRESH_INTERVAL_MS = 3000  # 网络连接刷新间隔（毫秒）

# 日志
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# 超时设置
DEFAULT_TIMEOUT_SEC = 8.0
SIGNATURE_VERIFY_TIMEOUT_SEC = 30.0

# 规则引擎
MAX_RULE_DISPLAY_LENGTH = 200  # 规则匹配详情截断长度
