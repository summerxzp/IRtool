# 优化任务板（给开发者和 AI 协作使用）

状态说明：`TODO` / `DOING` / `DONE`  
优先级说明：`P0`（高） `P1`（中） `P2`（低）

## 当前任务

1. `P0 DONE` 隐藏 Skill Scan Tab（功能待完善后重新开放）
- 目标：因 Skill Scan 功能尚未完善，暂时隐藏该 Tab，待后续功能成熟后再开放。
- 影响文件：`d:\project\sectool_codex\main.py`
- 实施结果：已注释 SkillScanTab 的导入和 Tab 添加代码，保留所有实现代码供后续使用。
- 时间：2026-02-14

2. `P0 DONE` 注释 Workspace 右键微步查询功能
- 目标：暂时禁用 Workspace Tab 右键菜单中的微步查询功能（单条和批量）。
- 影响文件：`d:\project\sectool_codex\ui\workspace_tab.py`
- 实施结果：已注释右键菜单中的"微步查询（当前条目）"和"微步批量查询（当前结果）"功能代码，保留实现供后续恢复。
- 时间：2026-02-14

3. `P0 DONE` Workspace 规则类型筛选优化
- 目标：修改规则类型筛选默认只选 IP，并添加全选/全部取消按钮提升操作效率。
- 影响文件：`d:\project\sectool_codex\ui\workspace_tab.py`
- 实施结果：默认仅选中 IP 类型；新增"全选"和"全部取消"按钮及对应方法 `_select_all_rule_types` / `_deselect_all_rule_types`。
- 时间：2026-02-14

4. `P0 DONE` Workspace 规则扫描结果展示优化
- 目标：优化规则扫描结果的显示方式，使 IP 扫描结果更清晰，规则名称更直观。
- 影响文件：`d:\project\sectool_codex\ui\workspace_results_presenter.py`、`d:\project\sectool_codex\ui\workspace_rule_dialogs.py`
- 实施结果：
  - IP 匹配时 Matched 列只显示 IP 地址（从 detail.matched_ip 获取）
  - Source 列显示规则名称（family）而非 "Rule Scan"
  - 规则详情中的 Note 添加 "Note:" 前缀
  - 规则管理对话框表头改为中文："规则名称"、"字段"、"匹配类型"、"匹配值"、"严重级别"、"发现日期"、"备注"
  - 规则编辑对话框标签 "家族" 改为 "规则名称"，变量名 `edt_family` 改为 `edt_rule_name`
- 时间：2026-02-14

5. `P0 DONE` IOC 导入功能增强
- 目标：优化 IOC 导入体验，支持直接粘贴文本内容。
- 影响文件：`d:\project\sectool_codex\ui\workspace_rule_dialogs.py`
- 实施结果：
  - 新增 `IOCImportDialog` 对话框类，使用表格形式展示数据
  - 表格列：值(必填)、类型、标签、动作、名称、时间、备注
  - 支持从Excel复制后直接粘贴到表格
  - 支持选择文件导入、清空、删除选中行
  - 自动识别制表符、逗号、空格等多种分隔符
  - 只提取关键字段：值、类型、名称、时间、备注
  - 修改 `_import_ioc` 方法，打开新对话框而非直接选择文件
- 时间：2026-02-14

2. `P0 DONE` 注释 Workspace "导出情报"按钮
- 目标：暂时隐藏微步相关的"导出情报"功能按钮，待功能完善后再开放。
- 影响文件：`d:\project\sectool_codex\ui\workspace_tab.py`
- 实施结果：已注释"导出情报"按钮的创建和添加代码，保留实现供后续恢复。
- 时间：2026-02-14

3. `P0 DONE` 优化 Autorun 类型规则扫描结果展示
- 目标：提升 Autorun 类型规则扫描结果的可读性，清晰展示原始持久化进程信息。
- 影响文件：`d:\project\sectool_codex\ui\workspace_tab.py`
- 实施结果：
  - Matched 列：显示命中的匹配值（如 "rundll32"）
  - Summary 列：显示 Entry | CommandLine
  - Source 列：显示规则名称（如 "银狐"）
  - 规则详情列：保持不变
- 时间：2026-02-14

4. `P0 DOING` 拆分 `workspace_tab.py` 的职责
- 目标：将规则管理、结果展示、处置动作从单文件拆分到独立组件。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/workspace_tab.py`
- 验收标准：主流程行为不变，文件体积明显下降，组件边界清晰。
- 进展（2026-02-13）：已完成阶段一，`RuleEditDialog` / `RuleManagerDialog` 已迁移到 `ui/workspace_rule_dialogs.py`。
- 下一步：继续拆分结果表格渲染与处置动作执行逻辑。

2. `P0 TODO` 建立 UI 性能基线与回归检查
- 目标：固化 Autoruns 关键交互指标，避免后续改动引入卡顿回退。
- 指标建议：过滤耗时、滚动流畅度、首屏渲染耗时、签名验证期间 UI 响应。
- 验收标准：输出一份可重复执行的性能记录文档（至少包含基线机型、样本条目数、统计方法）。

3. `P1 TODO` 统一风格令牌，减少散落样式
- 目标：将业务代码内硬编码样式收敛到 `ui/ui_style.py`。
- 影响文件：`ui/autoruns_tab.py`、`ui/network_tab.py`、`ui/workspace_tab.py`、`ui/ui_style.py`
- 验收标准：新增或修改样式时只需改 token，不需要在业务逻辑中全局搜改字符串。

4. `P1 TODO` 清理废弃入口与备份文件
- 目标：删除或隔离 `debug_main.py`、`ui/autoruns_tab_backup.py` 这类易引发误用的文件。
- 验收标准：保留单一真实入口，文档明确调试方式，避免团队成员基于旧文件重复开发。

5. `P1 TODO` 统一日志策略
- 目标：将 `print` 调试输出统一为 logger，支持级别和开关。
- 验收标准：默认运行日志干净，可按环境变量启用详细调试日志。

## 本次新增任务（新增）

6. `P0 TODO` 建立“功能点登记表”防重复机制
- 目标：在 README 维护“功能清单 + 代码归属 + 扩展点”，新增功能前先登记。
- 背景：当前多模块功能有交叉（搜索、规则、执行动作、导出），容易重复构建。
- 实施要求：
- 新功能提交时必须在 README 的“功能清单”增加一行记录。
- 记录最少包含：功能名、入口 UI、核心模块、是否已存在相似功能。
- 如已有相似功能，必须写“复用方案”而不是新建重复实现。
- 验收标准：连续两次迭代无重复功能分叉，新增功能均可在 README 快速定位代码归属。

7. `P0 DONE` 修复 Autoruns 右键签名验证中文乱码
- 目标：解决 `sigcheck` 输出中文显示为问号的问题。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/core/signature_parser.py`、`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/autoruns_tab.py`
- 实施结果：新增多编码自适应解码（优先系统编码 + UTF-16 + GBK/GB18030 等回退），签名验证线程已接入。

8. `P1 DONE` Autoruns 计划任务条目增加右键快速定位入口
- 目标：对 `Scheduled Tasks` 条目提供更直接的人工排查路径。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/autoruns_tab.py`
- 实施结果：新增“打开任务计划程序并复制任务标识”右键动作。

9. `P0 DOING` 工作台拆分阶段二：结果渲染与处置动作解耦
- 目标：将结果表格渲染和命令执行流程从 `WorkspaceTab` 继续拆分。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/workspace_tab.py`
- 验收标准：`WorkspaceTab` 仅保留编排职责，渲染与执行逻辑模块化。
- 进展（2026-02-13）：已新增 `ui/workspace_results_presenter.py` 和 `ui/workspace_action_executor.py`，并完成接线。
- 下一步：将规则扫描组装逻辑继续下沉到独立服务，减少 `WorkspaceTab` 业务复杂度。

10. `P1 DONE` 计划任务“精确定位”增强
- 目标：在已有“打开任务计划程序”基础上补充任务路径提示与复制策略（Entry/Location/LaunchString 优先级）。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/autoruns_tab.py`
- 验收标准：常见任务命名冲突场景下，分析员仍能快速定位目标任务。
- 实施结果：新增任务标识提取与候选列表展示，优先复制可定位标识。

11. `P1 DONE` 情报接口抽象层（微步/其他厂商）骨架
- 目标：定义统一 IOC 查询接口，避免将供应商 SDK/HTTP 逻辑直接写进 UI。
- 影响文件建议：`core/threat_intel/` 新目录（provider/base/service）。
- 验收标准：新增厂商仅实现 provider，不改 UI 主流程。
- 实施结果：已新增 `base.py`、`service.py`、`provider_weibu.py` 和 package 导出，支持单条/批量查询管线骨架。

12. `P1 DONE` 单条 IOC 右键查询（IP/Hash）
- 目标：在 Autoruns/Network/Workspace 结果上支持右键发起单条 IOC 查询。
- 依赖：任务 11。
- 验收标准：查询结果可在详情区或弹窗展示，失败可回退重试并给出错误信息。
- 实施结果：Workspace 右键已支持“微步查询（当前条目）”，可自动提取 IP/Hash 并展示查询结果。

13. `P1 DOING` 批量 IOC 查询任务队列（IP/Hash）
- 目标：支持对当前结果集批量查询，控制并发与速率限制，避免 API 封禁。
- 依赖：任务 11。
- 验收标准：支持暂停/继续/取消，结果可导出并带命中来源与时间戳。
- 进展（2026-02-13）：Workspace 已提供“微步批量查询（当前结果）”，支持去重、并发和基础 QPS 限速。
- 下一步：补充异步进度、暂停/取消与结果导出能力。

14. `P1 DONE` 常用 AI Agent Skill 路径体检（OpenClaw/ClaudeCode 等）
- 目标：扫描常见 skill 安装路径，识别可疑新增文件、异常修改时间、异常执行脚本。
- 影响文件建议：`core/skill_audit/` 与 `ui/workspace_tab.py`（触发入口）。
- 验收标准：可输出可疑 skill 清单（路径、hash、首次发现时间、风险原因）。
- 实施结果：已新增 `core/skill_audit/` 基础模块，完成首版 Skill 体检能力验证。
- 进展（2026-02-14）：Skill 扫描主入口已迁移到独立 `Skill Scan` Tab（`ui/skill_scan_tab.py`），不再塞在 Workspace 搜索区。

15. `P1 DOING` Skill 文件 Hash 联动情报查询（微步 + VirusTotal）
- 目标：对 skill 相关文件进行 hash 计算并联动情报平台查询，形成供应链侧风险辅助信号。
- 依赖：任务 11、14。
- 验收标准：支持单条右键查询与批量任务查询，查询结果可回写到工作台结果表。
- 进展（2026-02-14）：`Skill Scan` 已支持选中结果后手动触发“查询 VirusTotal / 查询 微步”（仅提交 hash，不上传文件）。
- 下一步：补充任务化查询进度、结果持久化与跨 Tab 联动视图。

16. `P1 DONE` Skill Hash -> 微步查询链路
- 目标：体检后可直接对可疑 skill 文件 hash 发起微步批量查询。
- 影响文件：`ui/workspace_tab.py`、`core/skill_audit/`、`core/threat_intel/`
- 进展（2026-02-13）：已支持体检后即时触发微步批量查询，且可复用“最近一次体检结果”再次查询。
- 进展（2026-02-13）：已支持导出最近一次查询结果为 JSON。
- 进展（2026-02-14）：查询入口已迁移至独立 `Skill Scan` Tab，避免 Workspace 职责持续膨胀。

17. `P2 DONE` VirusTotal Provider 骨架接入
- 目标：提前铺设多情报源扩展接口，避免后续改动主链路。
- 影响文件：`core/threat_intel/provider_virustotal.py`、`core/threat_intel/__init__.py`、`core/__init__.py`、`ui/workspace_tab.py`
- 实施结果：已完成 VT provider 占位实现与服务注册（当前 UI 默认仍以微步链路为主）。

18. `P0 DONE` 修复 Autoruns 右键“复制文件并加密压缩”闪退
- 目标：避免因 `pyzipper` 缺失或非法文件名导致 UI 异常退出。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/autoruns_tab.py`
- 实施结果：`pyzipper` 导入移入保护分支并新增 ImportError 提示；增加 Windows 文件名清洗函数。

19. `P1 DONE` 情报查询结果导出（JSON）
- 目标：支持导出最近一次微步查询结果，便于复盘与共享。
- 影响文件：`/Users/xiazhipeng/Desktop/codex/0213/sectool_codex/ui/workspace_tab.py`
- 实施结果：新增“导出情报”按钮，可导出最近一次单条/批量查询结果为 JSON。

20. `P0 DONE` Skill Scan 独立模块化重构（独立 Tab + 独立模型 + 独立扫描链路）
- 目标：将 Skill 相关扫描从 Workspace 解耦为一级 Tab，落实“发现 + 归集 + 呈现”边界。
- 影响文件：`main.py`、`ui/skill_scan_tab.py`、`core/skill_scan/`、`ui/workspace_tab.py`、`core/__init__.py`
- 实施结果：新增 `Skill Scan` 一级 Tab；新增 `SkillFileEntry/SkillScanConfig/SkillScanResult`；扫描按“路径构建→枚举→hash→归集”分阶段实现；默认手动触发 VT/微步查询且不自动联网。


## Skill Scan 需求基线（实施约束）
新增并实现一个【Skill Scan】功能模块。
这是一个“文件级 IOC 扫描”能力，不是杀毒，也不是 Autoruns 的附属功能，请严格按以下设计目标实现和重构。

====================
一、功能定位（必须理解）
====================
Skill Scan 的目标是：
- 扫描系统中“常见恶意 skill / 木马 / loader / dropper”容易落地的路径
- 枚举可疑文件并计算 hash（以 SHA256 为主）
- 为后续接入 VirusTotal / 微步 等威胁情报提供基础数据

该模块：
- 不直接判定恶意
- 不自动联网
- 只负责“发现 + 归集 + 呈现”

====================
二、UI 结构（新增 Tab）
====================

在主界面新增一个一级 Tab：
- 名称：Skill Scan

Skill Scan Tab 分为 3 个区域（自上而下）：

--------------------------------
【1】扫描配置区（Config Panel）
--------------------------------
- 扫描范围（Checkbox，可多选，默认勾选）：
  [x] AppData (%AppData%)
  [x] LocalAppData (%LocalAppData%)
  [x] ProgramData
  [x] Temp (%Temp%)
  [ ] Downloads (C:\Users\*\Downloads)

- 高级选项（折叠区域，默认收起）：
  - 自定义扫描路径（支持多行，每行一个路径）
  - 文件名过滤（可选）：
    - 精确文件名（如 chrome.exe）
    - 通配符（如 *.tmp, svchost*.exe）
  - 是否递归子目录（Checkbox，默认开启）

- 扫描按钮：
  [ Start Scan ]

--------------------------------
【2】扫描结果区（Result Table）
--------------------------------
表格列字段（固定）：
- 文件名
- 完整路径
- 文件大小
- 修改时间
- SHA256
- 来源路径类型（AppData / Custom / Temp 等）
- 状态（本地，默认值）

表格行为：
- 扫描完成后一次性填充
- 支持排序（大小 / 时间）
- 支持右键菜单：
  - 复制 SHA256
  - 打开文件所在目录
  - 标记为已确认安全（仅本地标记）

--------------------------------
【3】威胁情报操作区（Action）
--------------------------------
- 当选中一行或多行时，启用按钮：
  [ 查询 VirusTotal ]
  [ 查询 微步 ]

行为说明（UI 提示）：
- 查询仅提交 hash，不上传文件
- 默认不自动触发，必须人工点击

====================
三、数据结构设计（必须拆清）
====================

请新增独立的数据结构（不要复用 Workspace / Autoruns 的对象）：

SkillFileEntry：
- file_name: str
- full_path: str
- size: int
- mtime: datetime
- sha256: str
- source_type: str   # builtin / custom
- path_category: str # AppData / Temp / Custom
- tags: list[str]    # 如 confirmed_safe

SkillScanConfig：
- builtin_paths: list[str]
- custom_paths: list[str]
- filename_filters: list[str]
- recursive: bool

SkillScanResult：
- entries: list[SkillFileEntry]
- scan_time: datetime
- total_files: int

====================
四、扫描流程（必须分阶段）
====================

1. 构建扫描路径列表：
   - 根据 UI 勾选的内置路径
   - 合并自定义路径
   - 去重

2. 枚举文件：
   - 遍历路径（按 recursive 选项）
   - 应用文件名过滤（如果配置）
   - 只处理普通文件（跳过目录 / symlink）

3. 计算 hash：
   - 使用流式读取
   - 默认计算 SHA256
   - 单文件失败不影响整体扫描

4. 生成 SkillFileEntry 并收集

5. 扫描完成后：
   - 一次性更新 UI
   - 不边扫边刷（避免 UI 卡顿）

====================
五、架构约束（非常重要）
====================

- Skill Scan 必须是一个独立模块：
  - 独立 UI
  - 独立数据模型
  - 独立扫描逻辑

- 严禁：
  - 在扫描阶段自动联网
  - 在 Workspace 搜索框中复用 IP / hash 搜索逻辑
  - 将 Skill Scan 逻辑塞进 Autoruns 模块

====================
六、为未来预留的接口（先留空）
====================

请为威胁情报查询预留抽象接口，例如：

ThreatIntelProvider：
- query_hash(hash: str) -> dict

当前实现：
- 仅打印 / mock 返回
- 不需要真实接入 VT / 微步

====================
七、帮助说明（同步更新）
====================

在 Skill Scan 页面帮助中说明：
- 这是“可疑文件发现”功能，不是杀毒
- hash 查询是人工触发
- 结果需人工分析确认

====================
八、代码质量要求
====================

- 扫描逻辑与 UI 解耦
- 所有路径与规则可配置
- 保证未来可以：
  - 接入 VT / 微步
  - 与 Workspace 建立弱关联（例如标记来源）

按以上要求完成 Skill Scan 的完整实现或重构。


## Skill 重构任务分解（由“重构方向”拆分）

21. `P0 DONE` Skill Scan 路径策略收敛（高价值路径优先）
- 目标：从“大目录扫盘思路”收敛到工具链关键路径，减少噪音与扫描成本。
- 影响文件：`core/skill_scan/scanner.py`、`ui/skill_scan_tab.py`
- 验收标准：默认仅扫描 `%USERPROFILE%\\.claude`、`%USERPROFILE%\\.openclaw`、`%USERPROFILE%\\.codex`（可选 `.config` 路径），不再默认扫 AppData/Temp。
- 实施结果（2026-02-14）：已完成。

22. `P0 DONE` Skill 结果结构化增强（已知清单/恶意 Hash/风险标记）
- 目标：让 Skill 结果可被规则与后续情报模块消费，不再只是一张“纯文件列表”。
- 影响文件：`core/skill_scan/models.py`、`core/skill_scan/scanner.py`
- 验收标准：`SkillFileEntry` 至少包含 `is_known_skill_file`、`is_malicious_hash`、`risk_flags`。
- 实施结果（2026-02-14）：已完成。

23. `P0 DONE` Skill Scan 结果高亮与状态语义
- 目标：让分析员在列表中快速区分“命中恶意 Hash / 可疑 / 已知文件 / 已确认安全”。
- 影响文件：`ui/skill_scan_tab.py`
- 验收标准：状态列语义清晰，可疑与命中项可视化高亮。
- 实施结果（2026-02-14）：已完成。

24. `P0 TODO` Rule Engine 消费 Skill 结果（RuleHit）
- 目标：支持规则引擎同时消费 Persistence + Skill 结果，形成统一命中模型。
- 影响文件：`core/rule_engine.py`、`ui/workspace_tab.py`、`utils/search_result.py`
- 验收标准：可产生 `target_type=skill` 的命中结果，并在工作台统一展示。

25. `P1 TODO` 规则 explain 字段与 UI 帮助自动同步
- 目标：避免规则定义与帮助文案分裂。
- 影响文件：`data/rules.json`、`ui/workspace_rule_dialogs.py`
- 验收标准：规则 `explain` 可在规则管理/帮助区自动显示。

26. `P1 TODO` 规则类型分层（Persistence / Skill / Network / Mixed）
- 目标：为跨模块规则和未来特征接入提供边界。
- 影响文件：`core/rule_engine.py`、`data/rules.json`
- 验收标准：规则定义可声明 `target_type` 或等价字段，并据此过滤扫描输入。

27. `P1 TODO` 分层迁移蓝图落地（data_layer / scan_engine / rule_engine / ui）
- 目标：将当前 `core/` 内混合职责逐步迁移到明确分层。
- 影响文件：`core/`、`README.md`
- 验收标准：完成目录迁移草案与第一批适配，不破坏现有功能。

28. `P1 TODO` Skill 基线清单文件化
- 目标：将“已知 Skill 清单”“恶意 Hash 清单”外置到 data 文件，便于协作维护。
- 影响文件：`data/`、`core/skill_scan/scanner.py`、`ui/skill_scan_tab.py`
- 验收标准：支持从本地清单加载（不存在则回退默认内置集合）。

29. `P2 TODO` MCP / 工具链异常特征预留
- 目标：为后续“非官方 server / 可疑配置”规则接入预留字段。
- 影响文件：`core/skill_scan/models.py`、`core/rule_engine.py`
- 验收标准：数据模型可容纳 MCP 相关元数据，不影响当前流程。
