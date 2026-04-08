# Skill Scan 设计文档

本文档描述 Skill Scan 模块的设计目标和实现约束。

## 功能定位

Skill Scan 是一个"文件级 IOC 扫描"能力，不是杀毒，也不是 Autoruns 的附属功能。

### 目标
- 扫描系统中"常见恶意 skill / 木马 / loader / dropper"容易落地的路径
- 枚举可疑文件并计算 hash（以 SHA256 为主）
- 为后续接入 VirusTotal / 微步 等威胁情报提供基础数据

### 边界
- 不直接判定恶意
- 不自动联网
- 只负责"发现 + 归集 + 呈现"

## UI 结构

Skill Scan Tab 分为 3 个区域（自上而下）：

### 1. 扫描配置区

**扫描范围**（Checkbox，可多选）：
- `%USERPROFILE%\.claude`（默认勾选）
- `%USERPROFILE%\.openclaw`（默认勾选）
- `%USERPROFILE%\.codex`（默认勾选）
- `.config\claude`（可选）
- `.config\openclaw`（可选）

**高级选项**（折叠区域）：
- 自定义扫描路径（支持多行）
- 文件名过滤（精确/通配符）
- 是否递归子目录（默认开启）

### 2. 扫描结果区

**表格列**：
| 列名 | 说明 |
|------|------|
| 文件名 | - |
| 完整路径 | - |
| 文件大小 | 支持排序 |
| 修改时间 | 支持排序 |
| SHA256 | - |
| 来源类型 | builtin / custom |
| 状态 | 已知/恶意/可疑/安全 |

**右键菜单**：
- 复制 SHA256
- 打开文件所在目录
- 标记为已确认安全（本地标签）

### 3. 威胁情报操作区

选中结果后可触发：
- 查询 VirusTotal
- 查询微步

**注意**：查询仅提交 hash，不上传文件；默认不自动触发，需人工点击。

## 数据结构

```python
@dataclass
class SkillFileEntry:
    file_name: str
    full_path: str
    size: int
    mtime: datetime
    sha256: str
    source_type: str       # builtin / custom
    path_category: str     # AppData / Temp / Custom
    is_known_skill_file: bool
    is_malicious_hash: bool
    risk_flags: list[str]
    tags: list[str]

@dataclass
class SkillScanConfig:
    builtin_paths: list[str]
    custom_paths: list[str]
    filename_filters: list[str]
    recursive: bool

@dataclass
class SkillScanResult:
    entries: list[SkillFileEntry]
    scan_time: datetime
    total_files: int
```

## 扫描流程

```
1. 构建扫描路径列表
   └── 根据 UI 勾选 + 自定义路径 → 去重

2. 枚举文件
   └── 遍历路径（按 recursive 选项）
   └── 应用文件名过滤
   └── 只处理普通文件（跳过目录/symlink）

3. 计算 hash
   └── 流式读取，计算 SHA256
   └── 单文件失败不影响整体

4. 生成 SkillFileEntry
   └── 匹配已知清单
   └── 匹配恶意 Hash
   └── 风险标记

5. 更新 UI
   └── 扫描结束后一次性填充
   └── 不边扫边刷（避免 UI 抖动）
```

## 架构约束

### 必须遵守

- Skill Scan 必须是一个独立模块（独立 UI、数据模型、扫描逻辑）
- 扫描阶段不自动联网
- 不在 Workspace 搜索框中复用 IP/hash 搜索逻辑
- 不将 Skill Scan 逻辑塞进 Autoruns 模块

### 预留扩展

- `ThreatIntelProvider` 接口供后续情报查询使用
- 数据模型可容纳 MCP 相关元数据

## 当前状态

- **实现状态**: 基础功能已完成，Tab 暂时隐藏
- **隐藏原因**: 功能待完善后重新开放
- **代码位置**: `ui/skill_scan_tab.py`, `core/skill_scan/`