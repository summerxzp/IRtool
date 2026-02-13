# 优化任务板（给开发者和 AI 协作使用）

状态说明：`TODO` / `DOING` / `DONE`  
优先级说明：`P0`（高） `P1`（中） `P2`（低）

## 当前任务

1. `P0 DOING` 拆分 `workspace_tab.py` 的职责
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
- 实施结果：已新增 `core/skill_audit/` 模块与 Workspace “Skill体检”入口，支持常见路径扫描、hash 计算、可疑清单弹窗输出。

15. `P1 TODO` Skill 文件 Hash 联动情报查询（微步 + VirusTotal）
- 目标：对 skill 相关文件进行 hash 计算并联动情报平台查询，形成供应链侧风险辅助信号。
- 依赖：任务 11、14。
- 验收标准：支持单条右键查询与批量任务查询，查询结果可回写到工作台结果表。

16. `P1 DOING` Skill Hash -> 微步查询链路
- 目标：体检后可直接对可疑 skill 文件 hash 发起微步批量查询。
- 影响文件：`ui/workspace_tab.py`、`core/skill_audit/`、`core/threat_intel/`
- 进展（2026-02-13）：已支持体检后即时触发微步批量查询，且可复用“最近一次体检结果”再次查询。
- 下一步：将查询结果落表到 Workspace 结果列表，并支持导出。

17. `P2 DONE` VirusTotal Provider 骨架接入
- 目标：提前铺设多情报源扩展接口，避免后续改动主链路。
- 影响文件：`core/threat_intel/provider_virustotal.py`、`core/threat_intel/__init__.py`、`core/__init__.py`、`ui/workspace_tab.py`
- 实施结果：已完成 VT provider 占位实现与服务注册（当前 UI 默认仍以微步链路为主）。
