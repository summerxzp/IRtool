# 技术架构

本文档描述 IRtool 的技术架构设计。

## 总体分层

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                             │
│              (应用入口、主窗口装配)                        │
├─────────────────────────────────────────────────────────┤
│                        ui/                               │
│     (各业务 Tab、对话框、交互流程控制)                     │
├─────────────────────────────────────────────────────────┤
│                       core/                              │
│   (扫描解析、规则引擎、风险评估、数据仓库、情报接口)         │
├─────────────────────────────────────────────────────────┤
│                       utils/                             │
│     (导出、命令模板、路径解析、安全执行)                    │
├─────────────────────────────────────────────────────────┤
│              tools/           data/                      │
│        (外部二进制依赖)      (规则数据)                    │
└─────────────────────────────────────────────────────────┘
```

## 目录结构

```text
IRtool/
├── main.py                      # 应用入口
├── core/                        # 核心业务逻辑
│   ├── constants.py             # 全局常量
│   ├── autoruns_parser.py       # Autoruns 扫描解析
│   ├── signature_parser.py      # sigcheck 输出解析
│   ├── network_monitor.py       # 网络连接采集
│   ├── rule_engine.py           # 规则引擎
│   ├── risk_hint.py             # 风险评估
│   ├── icon_provider.py         # 图标缓存与角标
│   ├── data_store.py            # 内存数据仓库
│   ├── search_service.py        # 工作台搜索服务
│   ├── threat_intel/            # IOC 情报接口抽象层
│   ├── skill_scan/              # Skill Scan 独立模型
│   └── skill_audit/             # 旧版 Skill 模块（待迁移）
├── ui/                          # 界面层
│   ├── autoruns_tab.py          # 持久化检测主界面
│   ├── autoruns_tree_model.py   # 树形数据模型
│   ├── autoruns_scan_controller.py
│   ├── autoruns_detail_renderer.py
│   ├── autoruns_entry_mapper.py
│   ├── autoruns_signature_worker.py
│   ├── network_tab.py           # 网络监控界面
│   ├── skill_scan_tab.py        # Skill Scan 界面
│   ├── workspace_tab.py         # 工作台主界面
│   ├── workspace_rule_dialogs.py
│   ├── workspace_results_presenter.py
│   ├── workspace_action_executor.py
│   └── ui_style.py              # 样式令牌
├── utils/                       # 工具层
│   ├── safe_executor.py         # 命令执行封装
│   ├── command_template.py      # 命令模板
│   ├── exporter.py              # 导出工具
│   ├── path_resolver.py         # 路径解析
│   └── search_result.py         # 统一结果模型
├── tools/                       # 外部工具
│   ├── autorunsc64.exe
│   └── sigcheck64.exe
├── data/                        # 数据文件
│   └── rules.json
└── logs/                        # 运行日志（运行时创建）
```

## 关键数据流

### Autoruns 扫描流程

```
AutorunsTab               AutorunsScanController        AutorunsParser
    │                            │                            │
    │  1. 发起扫描请求            │                            │
    │ ────────────────────────>  │                            │
    │                            │  2. 启动 QThread            │
    │                            │ ─────────────────────────> │
    │                            │                            │  3. 调用 autorunsc64.exe
    │                            │                            │    解析 CSV 输出
    │                            │  4. 返回条目列表            │
    │                            │ <───────────────────────── │
    │  5. 更新模型                │                            │
    │ <────────────────────────  │                            │
    │                            │                            │
    ▼                            │                            │
AutorunsTreeModel ───────> QSortFilterProxyModel ───────> QTreeView
```

### 签名验证流程

```
用户操作 ────> SignatureVerifyWorker (QThread) ────> sigcheck64.exe
                      │
                      │  后台执行
                      ▼
            parse_sigcheck_output()
                      │
                      │  解析结果
                      ▼
              更新模型缓存 ────> 刷新详情面板
```

### 工作台规则扫描流程

```
WorkspaceTab
    │
    │  1. 收集 Autoruns/Network 数据
    ▼
RuleEngine.scan_entry()
    │
    │  2. 匹配规则（contains/regex/equals）
    ▼
SearchResult
    │
    │  3. 生成统一结果
    ▼
WorkspaceResultsPresenter ────> 结果表格
```

## 并发模型

| 场景 | 实现方式 | 说明 |
|------|----------|------|
| Autoruns 扫描 | QThread | 后台调用 autorunsc64.exe |
| 签名验证 | QThread | 后台调用 sigcheck64.exe |
| 网络刷新 | QTimer | 定时轮询网络连接 |
| Skill Scan | QThread | 后台文件枚举和 hash 计算 |
| 命令执行 | QThreadPool | 并发执行处置命令 |

**线程间通信**：使用 Qt signal/slot，避免直接跨线程操作 UI。

## 性能优化策略

### 数据模型优化

- `QAbstractItemModel + QSortFilterProxyModel` 实现 MVC 分离
- `_search_blob` 缓存：预计算搜索字段，减少重复字符串拼接
- `_display_values` 缓存：预计算显示字段，减少 `data()` 调用开销

### 渲染优化

- 图标两级缓存：原图缓存 + 风险角标缓存
- 风险等级缓存：避免重复风险评估计算
- 详情面板增量更新：控件复用，避免重复创建

### 交互优化

- 搜索防抖（debounce）：避免每击键触发全量过滤
- 签名验证异步化：不阻塞 UI 主线程
- 批量数据一次性填充：避免边扫边刷导致 UI 抖动

## 威胁情报架构

```
┌─────────────────────────────────────────────────────┐
│                ThreatIntelService                    │
│              (统一查询服务入口)                        │
├─────────────────────────────────────────────────────┤
│  ThreatIntelProvider (抽象接口)                       │
│       │                                              │
│       ├── WeibuProvider      (微步在线)               │
│       └── VirusTotalProvider (VirusTotal)            │
├─────────────────────────────────────────────────────┤
│  IOCQuery          IOCQueryResult                    │
│  (查询请求模型)     (查询结果模型)                      │
└─────────────────────────────────────────────────────┘
```

**设计原则**：
- Provider 抽象：新增厂商只需实现 provider 接口，不改 UI
- 批量查询支持：并发控制、QPS 限流、失败重试
- 结果可导出：JSON 格式，便于复盘共享

## 扩展点

### 新增规则匹配类型

在 `core/rule_engine.py` 的 `_match_rule_with_debug()` 方法中添加新的匹配逻辑。

### 新增威胁情报厂商

1. 在 `core/threat_intel/` 创建 `provider_xxx.py`
2. 继承 `ThreatIntelProvider` 并实现 `query()` 方法
3. 在 `ThreatIntelService` 中注册 provider

### 新增扫描模块

1. 在 `core/` 创建独立模块目录
2. 定义数据模型（Entry、Config、Result）
3. 实现扫描器（Scanner）
4. 在 `ui/` 创建对应 Tab
5. 在 `main.py` 中注册 Tab