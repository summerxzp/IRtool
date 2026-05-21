# IRtool 项目重构待办清单

> 日期：2026-05-19
> 版本：v1.1.3
> 目标：完成除威胁情报 Provider 外的所有审查问题修复

---

## 目录
- [P0 - 影响功能正确性](#p0---影响功能正确性)
- [P1 - 影响可维护性](#p1---影响可维护性)
- [P2 - 可优化但不紧急](#p2---可优化但不紧急)

---

## P0 - 影响功能正确性

### 问题1：规则 ID 重复导致规则被静默覆盖
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：[data/rules.json](file:///d:/project/IRtool/data/rules.json)、[core/rule_engine.py](file:///d:/project/IRtool/core/rule_engine.py)
- **修复内容**：
  - 第二个 `silverfox_inetpub_path` 改为 `silverfox_mfg_path`
  - rule_engine.py 添加重复 ID 检测逻辑
- **额外修复**：
  - 修复了 `silverfox_rundll_obfuscation` 规则的正则表达式语法错误
- **验证结果**：规则加载 269 条，校验错误 0 个

### 问题2：测试体系完全缺失
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：[tests/](file:///d:/project/IRtool/tests/)
- **修复内容**：
  - ✅ `RuleEngine` 测试：35 个测试覆盖规则加载、校验、contains/regex/equals/IP/hash 匹配、多条件、调试、保存加载
  - ✅ `PathResolver` 测试：19 个测试覆盖各路径获取和 resolve 方法
  - ✅ `SafeCommandExecutor` 测试：7 个测试覆盖 CommandResult、CommandStatus、CommandTask
  - ✅ `NetworkMonitor` 测试：4 个测试覆盖连接获取和过滤
  - ✅ conftest.py：PyQt6/psutil mock，测试无需安装 GUI 依赖
- **验证结果**：64 个测试全部通过

---

## P1 - 影响可维护性

### 问题5：`get_app_dir()` 重复实现 4 次
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：[utils/path_resolver.py](file:///d:/project/IRtool/utils/path_resolver.py)
- **修复内容**：
  - 创建 PathResolver 类和 PathScope 枚举
  - 提供统一的路径解析工具函数
  - 包含 resolve()、select_directory()、save_file() 等 UI 工具方法
- **验证结果**：导入正常，功能验证通过

### 问题6：`print()` 与 `logging` 混用（150 处）
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：
  - [core/autoruns_parser.py](file:///d:/project/IRtool/core/autoruns_parser.py)：34 处
  - [utils/safe_executor.py](file:///d:/project/IRtool/utils/safe_executor.py)：7 处
  - [ui/workspace_tab.py](file:///d:/project/IRtool/ui/workspace_tab.py)：2 处
- **修复内容**：将所有 `print()` 替换为 `LOGGER.info/debug/warning/error`
- **验证结果**：核心业务代码中无 print() 语句

### 问题7：`autoruns_tab.py` 过于臃肿（1653 行）
- **优先级**：P1
- **状态**：⏳ 待优化（延后）
- **相关文件**：[ui/autoruns_tab.py](file:///d:/project/IRtool/ui/autoruns_tab.py)
- **拆分方案**：
  - [ui/autoruns_context_menu.py](file:///d:/project/IRtool/ui/autoruns_context_menu.py) — 右键菜单逻辑
  - [ui/autoruns_file_ops.py](file:///d:/project/IRtool/ui/autoruns_file_ops.py) — 文件操作（加密、导出）
  - [ui/autoruns_navigation.py](file:///d:/project/IRtool/ui/autoruns_navigation.py) — 跳转逻辑（注册表、任务计划）
  - 保留 [autoruns_scan_controller.py](file:///d:/project/IRtool/ui/autoruns_scan_controller.py) 和 [autoruns_detail_renderer.py](file:///d:/project/IRtool/ui/autoruns_detail_renderer.py)
- **说明**：功能正常但文件过于臃肿，留待后续专项优化

### 问题8：构建脚本混乱（9 个 .ps1 + 3 个 .py）
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：[package/](file:///d:/project/IRtool/package/)
- **修复内容**：
  - 保留 [build-with-7z.ps1](file:///d:/project/IRtool/package/build-with-7z.ps1) 作为唯一主构建脚本
  - 其余 12 个脚本移入 `package/archive/`
  - 更新 `package/README.md` 明确唯一构建入口

### 问题9：依赖管理不分离
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：[pyproject.toml](file:///d:/project/IRtool/pyproject.toml)
- **修复内容**：通过 `pyproject.toml` 统一管理依赖，包含 `[project.optional-dependencies]` 分离开发依赖

---

## P2 - 可优化但不紧急

### 问题11：`config.json` 为空
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[config.json](file:///d:/project/IRtool/config.json)
- **修复内容**：定义 weibu_api_key 和 virustotal_api_key 两个字段（与代码中 config.get() 调用一致）

### 问题12：HTML 报告导出为半成品
- **优先级**：P2
- **状态**：✅ 已清理
- **相关文件**：[utils/exporter.py](file:///d:/project/IRtool/utils/exporter.py)
- **修复内容**：删除未完成的 `export_html_report()` 方法和未使用的 `from datetime import datetime`

### 问题13：`skill_audit` 旧模块未清理
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[core/skill_audit/](file:///d:/project/IRtool/core/skill_audit/)
- **修复内容**：
  - 从 `core/__init__.py` 移除 skill_audit 的导出
  - 在 `core/skill_audit/__init__.py` 添加 DeprecationWarning，引导使用 skill_scan

### 问题14：日志文件无轮转机制
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[main.py](file:///d:/project/IRtool/main.py)
- **修复内容**：`logging.FileHandler` → `logging.handlers.RotatingFileHandler`，maxBytes=10MB, backupCount=5

### 问题15：规则引擎 `contains` 匹配 field 选择不合理
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[core/rule_engine.py](file:///d:/project/IRtool/core/rule_engine.py)
- **修复内容**：
  - 审查全部 269 条规则，确认所有 field+type 组合均合理
  - 添加 `SUPPORTED_FIELDS` 常量，定义所有合法字段
  - 在 `_validate_all_rules()` 中添加未知 field 校验，发现不支持的字段时产生 `invalid_field` 错误

### 问题16：`.gitignore` 不完整
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[.gitignore](file:///d:/project/IRtool/.gitignore)
- **修复内容**：参考 GitHub Python.gitignore 模板补全，添加 Python、IDE、OS、环境变量、构建产物等分类

### 问题17：缺少 `pyproject.toml`
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：[pyproject.toml](file:///d:/project/IRtool/pyproject.toml)
- **修复内容**：创建 pyproject.toml，包含项目元数据、依赖、ruff/pytest 配置

---

## 修复汇总

### 已完成（14 项）
- ✅ 问题1：规则 ID 重复（rules.json + rule_engine.py）
- ✅ 问题2：核心测试编写（64 个测试全部通过）
- ✅ 问题5：统一 get_app_dir() 到 utils/path_resolver.py
- ✅ 问题6：替换 print() 为 logging（core/ui/utils）
- ✅ 问题8：构建脚本归档
- ✅ 问题9：依赖管理统一到 pyproject.toml
- ✅ 问题11：config.json schema 定义
- ✅ 问题12：HTML 报告半成品清理
- ✅ 问题13：skill_audit 旧模块清理 + DeprecationWarning
- ✅ 问题14：日志轮转机制
- ✅ 问题15：规则引擎 field 校验增强
- ✅ 问题16：.gitignore 补全
- ✅ 问题17：pyproject.toml 创建
- ✅ 修复正则表达式语法错误：`silverfox_rundll_obfuscation`

### 后续优化（1 项）
- ⏳ 问题7：拆分 autoruns_tab.py（功能正常，留待后续专项优化）

### 不实施
- ❌ 问题10：威胁情报 Provider（占位实现）
