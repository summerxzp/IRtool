# IRtool 项目规范化待办清单

> 日期：2026-05-21
> 目标：将项目工程化水平提升至专业开源标准

---

## 目录
- [后续优化](#后续优化)
- [P0 - 必须修复](#p0---必须修复)
- [P1 - 强烈建议修复](#p1---强烈建议修复)
- [P2 - 建议改进](#p2---建议改进)

---

## 后续优化

### T19：autoruns_tab.py 拆分重构
- **优先级**：P1（延后）
- **状态**：⏳ 待优化
- **相关文件**：`ui/autoruns_tab.py`（1653 行）
- **优化方案**：
  1. 拆分 `ui/autoruns_context_menu.py` — 右键菜单逻辑
  2. 拆分 `ui/autoruns_file_ops.py` — 文件操作（加密、导出）
  3. 拆分 `ui/autoruns_navigation.py` — 跳转逻辑（注册表、任务计划）
  4. 保留 `autoruns_scan_controller.py` 和 `autoruns_detail_renderer.py`
- **说明**：功能正常但文件过于臃肿，影响可维护性，留待后续专项优化

---

## P0 - 必须修复

### T01：package/build-venv/ 被提交到 Git 仓库
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：`.gitignore`、`package/build-venv/`
- **修复内容**：
  1. `.gitignore` 添加 `package/build-venv/`、`package/.venv/` 等完整条目
  2. 经确认 build-venv 未被 Git 追踪（已在旧 .gitignore 中），无需 `git rm`

### T02：缺少 LICENSE 文件
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：`LICENSE`
- **修复内容**：创建 MIT License 全文，署名 summerxzp

### T03：缺少 pyproject.toml
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：`pyproject.toml`、`core/constants.py`、`package/build-with-7z.ps1`
- **修复内容**：
  1. 创建 `pyproject.toml`，包含项目元数据、依赖、工具配置
  2. `constants.py` 改为从 `pyproject.toml` 动态读取版本号（单一来源）
  3. `build-with-7z.ps1` 改为从 `pyproject.toml` 动态读取版本号
  4. 从 Git 移除过时的 `IRtool-v1.0.2.spec`

### T04：测试体系几乎为空
- **优先级**：P0
- **状态**：✅ 已修复
- **相关文件**：`tests/`
- **修复内容**：
  1. 添加 `tests/__init__.py`
  2. 添加 `tests/conftest.py`（PyQt6/psutil mock，测试无需安装 GUI 依赖）
  3. 编写 `test_rules.py`：35 个测试覆盖 RuleEngine 加载、校验、contains/regex/equals/IP/hash 匹配、多条件、调试、保存加载
  4. 编写 `test_path_resolver.py`：19 个测试覆盖 PathResolver 各路径获取和 resolve 方法
  5. 编写 `test_safe_executor.py`：7 个测试覆盖 CommandResult、CommandStatus、CommandTask

---

## P1 - 强烈建议修复

### T05：.gitignore 不完整
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：`.gitignore`
- **修复内容**：参考 GitHub Python.gitignore 模板补全，添加 Python、IDE、OS、环境变量、构建产物等分类

### T06：Git 提交信息不规范
- **优先级**：P1
- **状态**：✅ 已修复
- **修复内容**：
  1. 创建 `.gitmessage` 提交模板
  2. 在 CONTRIBUTING.md 中补充 Conventional Commits 规范说明

### T07：构建脚本混乱
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：`package/`
- **修复内容**：
  1. 保留 `build-with-7z.ps1` 作为唯一主构建脚本
  2. 其余 12 个脚本移入 `package/archive/`
  3. 更新 `package/README.md` 明确唯一构建入口

### T08：版本号不一致
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：`pyproject.toml`、`core/constants.py`、`package/build-with-7z.ps1`、`Release.md`
- **修复内容**：
  1. 版本号单一来源：`pyproject.toml` 的 version 字段
  2. constants.py 和 build-with-7z.ps1 均从 pyproject.toml 动态读取
  3. 精简 Release.md，移除过时版本信息
  4. 从 Git 移除过时的 IRtool-v1.0.2.spec

### T09：bare except 仍在使用
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：`main.py:103`
- **修复内容**：`except:` → `except Exception:`

### T10：safe_executor.py 中残留 traceback.print_exc()
- **优先级**：P1
- **状态**：✅ 已修复
- **相关文件**：`utils/safe_executor.py:124-126`
- **修复内容**：替换为 `LOGGER.error(..., exc_info=True)`，移除 `import traceback`

---

## P2 - 建议改进

### T11：README.md 需要增强
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`README.md`
- **修复内容**：
  1. 添加版本/许可证/Python/平台徽章
  2. 补充虚拟环境创建步骤和开发模式安装
  3. 完善项目结构（添加每个文件的说明）
  4. 添加测试和打包章节
  5. 添加常见问题 FAQ

### T12：config.json 为空
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`config.json`
- **修复内容**：定义 weibu_api_key 和 virustotal_api_key 两个字段（与代码中 config.get() 调用一致）

### T13：日志无轮转机制
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`main.py:49`
- **修复内容**：`logging.FileHandler` → `logging.handlers.RotatingFileHandler`，maxBytes=10MB, backupCount=5

### T14：缺少代码风格工具配置
- **优先级**：P2
- **状态**：✅ 已配置（基础）
- **修复内容**：在 `pyproject.toml` 中添加 ruff 和 pytest 配置

### T15：skill_audit 旧模块未清理
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`core/skill_audit/`、`core/__init__.py`
- **修复内容**：
  1. 从 `core/__init__.py` 移除 skill_audit 的导出（确认 UI 层和 main.py 均未使用）
  2. 在 `core/skill_audit/__init__.py` 添加 DeprecationWarning，引导使用 skill_scan

### T16：文件命名不一致
- **优先级**：P2
- **状态**：✅ 已修复
- **修复内容**：
  1. 删除 `trea_project_rules.md`（与 `.trae/rules/project_rules.md` 重复）
  2. 将 `test_ioc_samples.txt` 移入 `data/`

### T17：缺少类型注解
- **优先级**：P2
- **状态**：✅ 已修复
- **修复内容**：
  1. 在 `rule_engine.py` 中定义 `ScanEntry(TypedDict)` 类型
  2. `scan_entry()` 方法参数添加类型注解：`entry: ScanEntry, allowed_types: Optional[Set[str]], debug: bool`
  3. 从 `core/__init__.py` 导出 `ScanEntry`

### T18：轻量 CI（可选）
- **优先级**：P2
- **状态**：✅ 已修复
- **修复内容**：添加 `.github/workflows/ci.yml`，Windows + Python 3.11 + pytest，仅 push/PR 触发

### T20：HTML 报告导出半成品清理
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`utils/exporter.py`
- **修复内容**：删除未完成的 `export_html_report()` 方法和未使用的 `from datetime import datetime`

### T21：规则引擎 field 校验增强
- **优先级**：P2
- **状态**：✅ 已修复
- **相关文件**：`core/rule_engine.py`
- **修复内容**：
  1. 添加 `SUPPORTED_FIELDS` 常量，定义所有合法字段
  2. 在 `_validate_all_rules()` 中添加未知 field 校验，发现不支持的字段时产生 `invalid_field` 错误
  3. 审查全部 269 条规则，确认所有 field+type 组合均合理

---

## 修复汇总

### 已完成（20 项）
- ✅ T01：.gitignore 完善 + build-venv 排除
- ✅ T02：LICENSE 文件创建
- ✅ T03：pyproject.toml 创建 + 版本号统一
- ✅ T04：核心测试编写（64 个测试全部通过）
- ✅ T05：.gitignore 补全
- ✅ T06：Git 提交规范 + .gitmessage 模板
- ✅ T07：构建脚本归档
- ✅ T08：版本号单一来源
- ✅ T09：bare except 修复
- ✅ T10：traceback.print_exc() 替换
- ✅ T11：README 增强（徽章、安装步骤、FAQ）
- ✅ T12：config.json schema 定义
- ✅ T13：日志轮转机制
- ✅ T14：ruff/pytest 基础配置
- ✅ T15：skill_audit 旧模块清理 + DeprecationWarning
- ✅ T16：文件命名清理
- ✅ T17：ScanEntry TypedDict 类型注解
- ✅ T18：轻量 CI (GitHub Actions)
- ✅ T20：HTML 报告半成品清理
- ✅ T21：规则引擎 field 校验增强

### 后续优化（1 项）
- ⏳ T19：autoruns_tab.py 拆分重构（1653 行 → 多模块）
