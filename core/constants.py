# core/constants.py
"""全局常量定义"""

# 应用信息
APP_NAME = "终端安全检测工具"
APP_ID = "com.internal.IRtool"
APP_VERSION = "1.0.2"
BUILD_TYPE = "release"  # release | dev
BUILD_DATE = "2026-04-10"

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
