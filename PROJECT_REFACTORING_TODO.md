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
- **状态**：待修复
- **相关文件**：[tests/](file:///d:/project/IRtool/tests/)
- **测试内容**：
  - [ ] `RuleEngine` 测试：规则加载、ID 唯一性、正则匹配、IP 匹配、contains 匹配
  - [ ] `AutorunsParser._parse_csv()` 测试：用 mock CSV 数据验证解析
  - [ ] `NetworkMonitor.get_connections()` 测试：验证连接列表格式
  - [ ] `SafeCommandExecutor` 测试：验证命令执行、超时、错误处理
- **预计工作量**：4 小时

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
- **状态**：待修复
- **相关文件**：[ui/autoruns_tab.py](file:///d:/project/IRtool/ui/autoruns_tab.py)
- **拆分方案**：
  - [ui/autoruns_context_menu.py](file:///d:/project/IRtool/ui/autoruns_context_menu.py) — 右键菜单逻辑
  - [ui/autoruns_file_ops.py](file:///d:/project/IRtool/ui/autoruns_file_ops.py) — 文件操作（加密、导出）
  - [ui/autoruns_navigation.py](file:///d:/project/IRtool/ui/autoruns_navigation.py) — 跳转逻辑（注册表、任务计划）
  - 保留 [autoruns_scan_controller.py](file:///d:/project/IRtool/ui/autoruns_scan_controller.py) 和 [autoruns_detail_renderer.py](file:///d:/project/IRtool/ui/autoruns_detail_renderer.py)
- **预计工作量**：4 小时

### 问题8：构建脚本混乱（9 个 .ps1 + 3 个 .py）
- **优先级**：P1
- **状态**：待修复
- **相关文件**：[package/](file:///d:/project/IRtool/package/)
- **修复方案**：
  - 保留 [build-with-7z.ps1](file:///d:/project/IRtool/package/build-with-7z.ps1) 作为唯一主构建脚本
  - 将其他脚本归档到 `package/archive/`
  - 在 `package/README.md` 中说明唯一构建入口
- **预计工作量**：30 分钟

### 问题9：依赖管理不分离
- **优先级**：P1
- **状态**：待修复
- **相关文件**：[requirements.txt](file:///d:/project/IRtool/requirements.txt)
- **修复方案**：
  - 保留 [requirements.txt](file:///d:/project/IRtool/requirements.txt) 为仅运行时依赖
  - 创建 [requirements-dev.txt](file:///d:/project/IRtool/requirements-dev.txt) 为开发/测试/打包依赖
- **预计工作量**：15 分钟

---

## P2 - 可优化但不紧急

### 问题11：`config.json` 为空
- **优先级**：P2
- **状态**：待实现
- **相关文件**：[config.json](file:///d:/project/IRtool/config.json)
- **修复方案**：定义配置 schema（API keys、窗口布局、规则路径等）
- **预计工作量**：1 小时

### 问题12：HTML 报告导出为半成品
- **优先级**：P2
- **状态**：待完成
- **相关文件**：[utils/exporter.py](file:///d:/project/IRtool/utils/exporter.py)
- **修复方案**：完成 `export_html_report()` 的表格内容填充
- **预计工作量**：1.5 小时

### 问题13：`skill_audit` 旧模块未清理
- **优先级**：P2
- **状态**：待清理
- **相关文件**：[core/skill_audit/](file:///d:/project/IRtool/core/skill_audit/)
- **修复方案**：明确迁移计划，添加 `@deprecated` 标注或删除
- **预计工作量**：30 分钟

### 问题14：日志文件无轮转机制
- **优先级**：P2
- **状态**：待实现
- **相关文件**：[main.py:54](file:///d:/project/IRtool/main.py#L54)
- **修复方案**：改用 `logging.handlers.RotatingFileHandler`
- **预计工作量**：15 分钟

### 问题15：规则引擎 `contains` 匹配 field 选择不合理
- **优先级**：P2
- **状态**：待审查
- **相关文件**：[core/rule_engine.py:265](file:///d:/project/IRtool/core/rule_engine.py#L265)
- **修复方案**：审查所有规则的 `field` 选择，添加警告
- **预计工作量**：1 小时

### 问题16：`.gitignore` 不完整
- **优先级**：P2
- **状态**：待更新
- **相关文件**：[.gitignore](file:///d:/project/IRtool/.gitignore)
- **修复方案**：添加 `dist/`、`build/`、`.idea/`、`.vscode/`、`*.spec`
- **预计工作量**：10 分钟

### 问题17：缺少 `pyproject.toml`
- **优先级**：P2
- **状态**：待创建
- **相关文件**：`pyproject.toml`（待创建）
- **修复方案**：添加项目元数据、lint 配置
- **预计工作量**：30 分钟

---

## 本次修复汇总

### 本次已完成
- ✅ 问题1：规则 ID 重复（rules.json + rule_engine.py）
- ✅ 问题5：统一 get_app_dir() 到 utils/path_resolver.py
- ✅ 问题6：替换 print() 为 logging（core/ui/utils）
- ✅ 修复正则表达式语法错误：`silverfox_rundll_obfuscation`
- ✅ 重新打包：`package/dist/IRtool-v1.1.3-7z.exe` (53.6 MB)

### 不实施
- ❌ 问题10：威胁情报 Provider（占位实现）

---

## 待处理

### P0 - 待处理
- [ ] 问题2：编写核心测试（RuleEngine、AutorunsParser）

### P1 - 待处理
- [ ] 问题7：拆分 autoruns_tab.py
- [ ] 问题8：清理构建脚本
- [ ] 问题9：分离依赖文件

### P2 - 待处理
- [ ] 问题11：config.json schema
- [ ] 问题12：HTML 报告导出
- [ ] 问题13：skill_audit 旧模块清理
- [ ] 问题14：日志轮转机制
- [ ] 问题15：规则引擎 field 审查
- [ ] 问题16：.gitignore 更新
- [ ] 问题17：pyproject.toml 创建

---

## 执行顺序建议
1. **立即**：问题1（已处理）
2. **本周**：问题5 → 问题6 → 问题8 → 问题9 → 问题7 → 问题2
3. **下周**：问题11-17

---

## 总预计工作量
- P0：4 小时 10 分钟（测试待完成）
- P1：7 小时 45 分钟（部分已完成）
- P2：6 小时 35 分钟
- **总计**：约 18.5 小时（本次完成约 5 小时）
