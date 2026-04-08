# 终端安全检测工具（IRtool）

面向 Windows 终端应急响应场景的本地桌面工具，核心目标是帮助分析人员快速发现网络异常、持久化启动项异常，并在工作台进行规则化关联排查与处置辅助。

## 1. 项目定位

### 1.1 使用场景
- 在疑似中毒的终端上首次运行，快速获取现场信息。
- 辅助定位恶意木马驻留点（自启动项、异常命令行、可疑路径、可疑网络连接）。
- 支持人工复核与处置动作（查看详情、删除启动项、导出、加密压缩等）。

### 1.2 设计边界
- 平台：仅 Windows。
- 部署：离线可运行，依赖本地工具 `autorunsc64.exe`、`sigcheck64.exe`。
- 性能取向：优先保证首轮扫描与大列表滚动可用性，不依赖二次启动缓存优化。

## 2. 功能清单（防重复建设）

### 2.1 网络监控（`ui/network_tab.py`）
- 实时采集网络连接（TCP/UDP、PID、进程路径、状态）。
- 支持状态过滤、关键词搜索、排序、自动刷新间隔。
- 支持终止进程、CSV 导出、历史连接保留与清空。
- 支持右键在资源管理器定位进程文件。

### 2.2 持久化检测（`ui/autoruns_tab.py`）
- 调用 Sysinternals Autoruns 命令行工具扫描自启动项。
- 支持分类过滤、关键词过滤、仅显示可疑项。
- 支持风险提示（颜色+图标角标）、详情面板、跳转联动。
- 支持单条 hash 计算、单条签名重验（异步线程）、删除条目、CSV 导出。
- 对计划任务条目支持右键打开任务计划程序，并复制任务标识辅助定位。
- `sigcheck` 输出增加多编码解码回退，降低中文路径/中文发布者乱码概率。
- 右键“复制文件并加密压缩”已增加依赖缺失保护与文件名清洗，避免异常闪退。

### 2.3 工作台（`ui/workspace_tab.py`）
- 汇总搜索（当前以 Autoruns 关键字检索为主）。
- 规则扫描（Rule Engine 驱动，支持 IOC 导入、规则管理、规则测试）。
- 处置辅助命令模板（解锁、取所有权、删除、压缩）与安全执行封装。
- 与 Autoruns Tab 双向联动（搜索跳转/定位条目）。
- 规则编辑与规则管理对话框已拆分到 `ui/workspace_rule_dialogs.py`，降低主 Tab 文件复杂度。
- 结果表格渲染与命令执行流程已拆分到 `ui/workspace_results_presenter.py` / `ui/workspace_action_executor.py`。
- 右键已支持微步单条查询与批量查询 UI 链路（IOC 自动提取 IP/Hash）。

### 2.4 规则系统（`core/rule_engine.py`）
- 规则类型：`contains` / `regex` / `equals`。
- 规则字段覆盖：命令行、路径、哈希、IP、发布者等。
- 支持规则校验、批量测试、导入导出、默认规则兜底。
- **规则管理对话框**（`ui/workspace_rule_dialogs.py`）：
  - 表格列：ID、规则名称、字段、匹配类型、匹配值、严重级别、发现日期、备注。
  - 支持双击编辑、下拉框选择字段/匹配类型/严重级别。
  - 支持规则搜索（按规则名称/字段/匹配值/备注过滤）。
  - 支持新增、删除、导入、导出规则。
  - 支持规则测试（验证规则有效性）。
  - 支持导入 IOC（自动转换为规则）。
- **规则编辑对话框**（`ui/workspace_rule_dialogs.py`）：
  - 表单字段：规则ID、规则名称、字段、匹配类型、匹配值、严重级别、发现日期、备注。
  - 支持规则测试按钮，实时验证规则匹配效果。
  - 数据模型字段名保持为 `family`（历史兼容），UI 层使用 `edt_rule_name` 变量。

### 2.5 数据与检索
- `DataStore`（`core/data_store.py`）：
  统一内存数据仓库，负责 Autoruns/Network 数据广播。
- `SearchService`（`core/search_service.py`）：
  负责对 DataStore 数据做归一化与关键词检索。

### 2.6 外部情报接口（骨架已落地）
- 目标：支持微步等威胁情报服务，对单条或批量 IP/Hash 做查询。
- 规划原则：通过统一 provider 抽象接入，避免 UI 与厂商 API 强耦合。
- 执行形态：右键单条查询 + 批量任务队列查询（含限流、失败重试、导出）。
- 当前实现：`core/threat_intel/` 已提供 `IOCQuery/IOCQueryResult`、provider 抽象、批量查询服务与 `WeibuProvider`、`VirusTotalProvider` 占位实现。
- 当前 UI：Workspace 结果右键支持“微步查询（当前条目）”与“微步批量查询（当前结果）”。
- 当前 UI：支持导出最近一次情报查询结果（JSON）。

### 2.7 Skill Scan (`ui/skill_scan_tab.py`)
- **状态：暂时隐藏（2026-02-14）** - 功能待完善后重新开放，代码保留在仓库中。
- 定位：文件级 IOC 发现能力（发现 + 归集 + 呈现），不自动判恶、不自动联网。
- 扫描范围：高价值工具链路径（`%USERPROFILE%\\.claude` / `.openclaw` / `.codex`，可选 `.config\\claude` / `.config\\openclaw`）+ 自定义路径。
- 扫描能力：支持递归开关、文件名精确匹配/通配符过滤、流式 SHA256 计算。
- 结果增强：支持"已知 Skill 清单"匹配、恶意 Hash 清单命中、风险标记（扩展名/命名特征/未知文件）。
- 结果展示：固定字段表格（文件名/路径/大小/时间/SHA256/来源类型/状态），支持按大小和时间排序与风险高亮。
- 右键动作：复制 SHA256、打开文件所在目录、标记"已确认安全"（本地标签）。
- 情报联动：选中结果后手动触发 VirusTotal/微步 hash 查询（仅提交 hash，不上传文件）。

## 3. 技术架构

## 3.1 总体分层
- `main.py`：应用入口、主窗口与 Tab 装配、管理员模式处理。
- `core/`：扫描解析、规则引擎、风险评估、图标提供、数据仓库。
- `ui/`：各业务 Tab 与交互流程控制。
- `utils/`：导出、命令模板、路径解析、安全执行、通用结果模型。
- `tools/`：外部二进制依赖（autoruns/sigcheck）。
- `data/`：规则数据。

## 3.2 关键数据流

### Autoruns 流
1. `AutorunsTab` 发起扫描请求。
2. `AutorunsScanController` 启动 `AutorunsScanWorker`（QThread）。
3. `AutorunsParser` 调用 `autorunsc64.exe`，解析 CSV 为条目。
4. UI Model 通过 `map_to_model_entry` 归一化并缓存展示字段。
5. `QSortFilterProxyModel` 执行前端过滤。
6. 详情区由 `AutorunsDetailRenderer` 渲染。

### 签名验证流
1. 用户触发“重新验证签名”。
2. `SignatureVerifyWorker` 后台调用 `sigcheck64.exe`。
3. `parse_sigcheck_output` 解析输出。
4. 模型更新缓存并刷新当前选中详情。

### 工作台规则流
1. 工作台收集当前 Autoruns/Network 数据。
2. `RuleEngine` 按允许类型匹配规则。
3. 结果生成统一 `SearchResult`，显示于工作台结果表格。
4. 可触发跳转、复制、执行处置命令等动作。

### Skill Scan 流
1. `SkillScanTab` 组装 `SkillScanConfig`（内置路径 + 自定义路径 + 过滤 + 递归开关）。
2. `SkillScanWorker` 在后台线程调用 `SkillScanScanner.scan()`。
3. 扫描器按阶段执行：路径构建 -> 文件枚举 -> SHA256 计算 -> `SkillFileEntry` 归集。
4. 扫描结束后一次性刷新表格（不边扫边刷），降低大批量结果下的 UI 抖动。
5. 分析员手动选择条目触发微步/VT 查询，结果通过统一 `ThreatIntelService` 返回。

## 3.3 并发模型
- QThread：Autoruns 扫描、签名重验、网络刷新、Skill Scan 后台扫描。
- UI 线程：渲染与交互。
- 线程间通信：Qt signal/slot，避免直接跨线程操作 UI。

## 3.4 目标分层（迁移中）
- `data_layer`：统一结构化资产模型（PersistenceEntry / SkillEntry / RuleHit），不包含 UI 逻辑。
- `scan_engine`：按模块产出标准化扫描结果（persistence_scan / skill_scan / rule_scan）。
- `rule_engine`：规则定义与匹配核心（规则文件 + matcher），与 UI 解耦。
- `ui`：只负责编排与展示，消费 scan/rule 结果，不内嵌扫描核心逻辑。
- 当前状态：项目已完成 `Skill Scan` 独立化；其余模块按任务板分阶段迁移。

## 4. 当前已实现的性能关键点

- Autoruns 列表使用 `QAbstractItemModel + QSortFilterProxyModel`，并有 `_search_blob` 缓存。
- 风险等级缓存与前景/背景刷子缓存，减少重复计算。
- 图标两级缓存（原图缓存 + 风险角标缓存）与分批预热。
- 搜索过滤防抖（debounce）避免每击键全量过滤。
- 详情面板抽取为 `AutorunsDetailRenderer`，采用控件复用与增量更新。
- 签名验证改为异步线程，避免 UI 主线程阻塞。

## 5. 模块职责边界（开发规范）

### 5.1 不要跨层
- `ui/` 只编排交互和展示，不实现规则匹配核心逻辑。
- `core/` 不依赖具体 UI 控件类型。
- `utils/` 只放可复用通用能力，不放业务编排。

### 5.2 新功能接入前检查（避免重复实现）
1. 先查 `ui/workspace_tab.py` 是否已有同类交互。
2. 先查 `core/rule_engine.py` 是否已有同类匹配类型。
3. 先查 `utils/command_template.py` 是否已有同类命令模板。
4. 先查 `ui/autoruns_tab.py` 是否已有同类右键动作。
5. 若为样式调整，优先修改 `ui/ui_style.py` 令牌，不在业务代码散落硬编码。

### 5.3 代码约定
- 优先小函数、单一职责，避免超长方法继续膨胀。
- 高风险操作（删除/执行命令）必须保留确认弹窗与失败提示。
- 新增后台任务必须走 QThread/线程池，不阻塞 UI。
- 新增功能需补充“入口点 + 数据流 + 影响范围”说明（可写入 PR 描述或任务卡）。

## 6. 目录速查

```text
IRtool/
├─ main.py                     # 应用入口与主窗口装配
├─ core/
│  ├─ autoruns_parser.py       # Autoruns 扫描、解析、删除、hash
│  ├─ signature_parser.py      # sigcheck 输出解析
│  ├─ network_monitor.py       # 网络连接采集
│  ├─ rule_engine.py           # 规则引擎
│  ├─ risk_hint.py             # 风险评估
│  ├─ icon_provider.py         # 图标缓存与角标
│  ├─ data_store.py            # 内存数据仓库
│  ├─ search_service.py        # 工作台搜索服务
│  ├─ threat_intel/            # IOC 情报接口抽象层
│  ├─ skill_scan/              # Skill Scan 独立模型与扫描逻辑
│  └─ skill_audit/             # 旧版 Skill 体检模块（待收敛/迁移）
├─ ui/
│  ├─ autoruns_tab.py          # 持久化检测主界面
│  ├─ autoruns_scan_controller.py
│  ├─ autoruns_detail_renderer.py
│  ├─ autoruns_entry_mapper.py
│  ├─ network_tab.py           # 网络监控界面
│  ├─ skill_scan_tab.py        # Skill Scan 独立界面
│  ├─ workspace_tab.py         # 工作台与规则管理
│  ├─ workspace_rule_dialogs.py # 规则编辑/规则管理对话框
│  ├─ workspace_results_presenter.py # 工作台结果表格渲染器
│  ├─ workspace_action_executor.py  # 工作台命令执行器
│  └─ ui_style.py              # 全局与模块样式令牌
├─ utils/
│  ├─ safe_executor.py         # 命令执行封装
│  ├─ command_template.py      # 命令模板
│  ├─ exporter.py              # 导出工具
│  ├─ path_resolver.py         # 路径作用域解析
│  └─ search_result.py         # 统一结果模型
├─ tools/
│  ├─ autorunsc64.exe
│  └─ sigcheck64.exe
└─ data/
   └─ rules.json
```

## 7. 本地开发运行

```bash
pip install -r requirements.txt
python main.py
```

可选调试日志：

```bash
set IRTOOL_DEBUG_LOG=1
python main.py
```

微步 API Key（可选）：

```bash
set IRTOOL_WEIBU_API_KEY=your_api_key
```

或写入 `config.json`：

```json
{
  "weibu_api_key": "your_api_key"
}
```

VirusTotal API Key（可选，预留）：

```bash
set IRTOOL_VT_API_KEY=your_api_key
```

或写入 `config.json`：

```json
{
  "virustotal_api_key": "your_api_key"
}
```

## 8. 后续优化方向（概要）

- 继续拆分 `workspace_tab.py`（规则管理、结果展示、执行动作分离）。
- 为关键路径建立统一性能基线（过滤耗时、滚动帧耗时、首屏加载耗时）。
- 统一 UI 样式令牌，减少散落样式字符串，提升一致性与可维护性。

## 9. 最近更新

- 2026-02-13：完成 `workspace_tab.py` 第一阶段拆分，将 `RuleEditDialog` 和 `RuleManagerDialog` 迁移到 `workspace_rule_dialogs.py`，功能行为保持不变。
- 2026-02-13：修复 Autoruns 右键签名验证编码链路，新增 `sigcheck` 多编码解码回退。
- 2026-02-13：为 Scheduled Tasks 条目新增“打开任务计划程序并复制任务标识”右键动作。
- 2026-02-13：完成 `WorkspaceTab` 阶段二拆分，新增结果渲染器与命令执行器模块。
- 2026-02-13：新增 `core/threat_intel/` 情报接口抽象层骨架（支持后续微步/多厂商接入）。
- 2026-02-13：打通 Workspace 微步查询 UI 链路（单条右键 + 批量查询入口）。
- 2026-02-13：新增 Skill 体检基础能力（常见路径扫描 + hash + 可疑清单），并在 Workspace 提供入口。
- 2026-02-13：打通 Skill 体检结果到微步 Hash 批量查询链路。
- 2026-02-13：新增 VirusTotal provider 骨架并完成服务注册（UI 默认仍使用微步）。
- 2026-02-13：修复 Autoruns 右键压缩闪退问题（`pyzipper` 缺失保护 + 文件名清洗）。
- 2026-02-13：新增情报查询结果 JSON 导出能力。
- 2026-02-14：新增独立 `Skill Scan` 一级 Tab，完成配置区/结果区/情报动作区三段式结构。
- 2026-02-14：新增 `core/skill_scan/`（`SkillFileEntry`、`SkillScanConfig`、`SkillScanResult`、`SkillScanScanner`），扫描按阶段解耦。
- 2026-02-14：Workspace 移除 Skill 专属按钮，Skill 能力迁移到独立 Tab，避免职责继续耦合。
- 2026-02-14：Skill Scan 改为高价值路径优先（`.claude/.openclaw/.codex`），不再默认扫 AppData/Temp。
- 2026-02-14：Skill 结果新增结构化判定字段（已知清单/恶意 Hash 命中/风险标记）并接入列表高亮。
