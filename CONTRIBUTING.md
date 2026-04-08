# 开发指南

本文档面向 IRtool 的开发者和贡献者。

## 开发环境

### 系统要求

- **操作系统**: Windows 10/11
- **Python**: 3.11+
- **依赖工具**: `autorunsc64.exe`、`sigcheck64.exe`（已包含在 `tools/` 目录）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行项目

```bash
# 普通模式
python main.py

# 调试模式（启用详细日志）
set IRTOOL_DEBUG_LOG=1
python main.py
```

### 运行测试

```bash
pytest tests/
```

## 项目结构

详见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 开发规范

### 分层原则

| 层级 | 职责 | 禁止 |
|------|------|------|
| `ui/` | 编排交互和展示 | 实现业务逻辑、依赖具体 UI 控件类型 |
| `core/` | 业务逻辑处理 | 依赖具体 UI 控件类型 |
| `utils/` | 可复用通用能力 | 放置业务编排逻辑 |

### 新功能接入检查清单

在新增功能前，请先检查：

1. [ ] `ui/workspace_tab.py` 是否已有同类交互？
2. [ ] `core/rule_engine.py` 是否已有同类匹配类型？
3. [ ] `utils/command_template.py` 是否已有同类命令模板？
4. [ ] `ui/autoruns_tab.py` 是否已有同类右键动作？
5. [ ] 样式调整是否可以复用 `ui/ui_style.py`？

### 代码约定

- **函数职责**：优先小函数、单一职责
- **高风险操作**：删除、执行命令等必须保留确认弹窗
- **后台任务**：必须使用 QThread/线程池，不阻塞 UI
- **新功能文档**：补充入口点、数据流、影响范围说明

### 样式规范

统一使用 `ui/ui_style.py` 中的样式令牌，避免在业务代码中散落硬编码样式。

```python
# 推荐
from ui.ui_style import AUTORUNS_CONTROL_HEIGHT

control.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)

# 不推荐
control.setFixedHeight(28)
```

### 日志规范

```python
import logging

LOGGER = logging.getLogger("IRtool.module_name")

# 使用 logger 而非 print
LOGGER.info(f"[Module] 操作完成: {result}")
LOGGER.error(f"[Module] 操作失败: {error}")
```

**调试日志开关**：
```python
DEBUG_LOG_ENABLED = os.getenv("IRTOOL_DEBUG_LOG", "0") == "1"

def _debug_log(msg: str) -> None:
    if DEBUG_LOG_ENABLED:
        LOGGER.debug(msg)
```

### 路径适配

支持源码运行和 PyInstaller 打包两种环境：

```python
def get_app_dir() -> Path:
    """获取应用根目录"""
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return Path(sys.executable).parent
    else:
        # 源码运行
        return Path(__file__).parent.parent
```

## 打包发布

详见 [Release.md](Release.md)。

### 快速打包

```powershell
# 默认模式：onedir-7z（推荐）
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1
```

### 发布检查清单

- [ ] 更新 `core/constants.py` 版本号
- [ ] 更新 `package/build-with-7z.ps1` 版本号
- [ ] 更新 `CHANGELOG.md` 版本日志
- [ ] 测试源码运行正常
- [ ] 测试打包后运行正常
- [ ] 验证工具调用正常（autoruns, sigcheck）
- [ ] 验证管理员权限申请

## 常见问题

### Q: 如何添加新的规则匹配类型？

在 `core/rule_engine.py` 的 `_match_rule_with_debug()` 方法中添加新的匹配逻辑。

### Q: 签名验证中文乱码？

检查 `core/signature_parser.py` 中的编码处理逻辑，支持多编码回退。