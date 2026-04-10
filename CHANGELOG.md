# 更新日志

所有重要的变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [1.0.2] - 2026-04-10

### 文档
- 重构项目文档结构
- 重写 README.md，按标准开源项目规范编写
- 新增 CHANGELOG.md 记录版本变更历史
- 新增 CONTRIBUTING.md 开发指南
- 新增 docs/ARCHITECTURE.md 技术架构文档
- 新增 docs/DESIGN-SKILL-SCAN.md Skill Scan 设计文档
- 删除冗余的 TASKS.md（内容已迁移）

### 重构
- 重命名项目 sectool_codex -> IRtool，更新所有路径引用
- 拆分 autoruns_tab.py (2197行) 为独立模块：
  - autoruns_tree_model.py: 树形模型和过滤代理
  - autoruns_signature_worker.py: 签名验证工作线程
- 提取魔法数字为常量 (窗口尺寸、线程数、超时等)
- 统一 import 顺序：标准库 → 第三方库 → 本地模块
- 添加 `__all__` 定义，明确模块导出接口
- 清理冗余文件：备份文件、临时测试脚本
- 更新 .gitignore 规则

### 修复
- 修复 utils/__init__.py 中 DataExporter 导入错误
- 修复 autoruns_tab.py 中 QElapsedTimer 和 QPalette 未定义错误
- 修复管理员权限申请逻辑，确保无权限时也能正常运行

## [1.0.1] - 2026-02-26

### 新增
- 规则引擎从 JSON 文件加载，移除硬编码规则
- 规则管理界面支持规则测试
- IOC 导入功能增强，支持直接粘贴文本内容

### 修复
- 规则管理界面匹配值截断显示问题
- Autoruns 右键签名验证中文乱码（多编码自适应解码）
- Autoruns 右键"复制文件并加密压缩"闪退问题

### 优化
- 升级 PyQt6 版本至 6.10.2
- Workspace 规则类型筛选默认只选 IP，新增全选/全部取消按钮
- Autoruns 计划任务条目增加右键快速定位入口

### 变更
- 工具名称从 sectool 更名为 IRtool

## [1.0.0] - 2026-02-14

### 新增
- 网络监控功能：实时采集网络连接，支持过滤、搜索、导出
- 持久化检测功能：调用 Sysinternals Autoruns 扫描自启动项
- 工作台功能：规则扫描、处置辅助命令模板
- 规则系统：支持 contains/regex/equals 三种匹配类型
- 威胁情报接口抽象层：支持微步、VirusTotal provider
- Skill Scan 模块：文件级 IOC 发现能力（暂时隐藏）
- onedir + 7z 自解压打包方案
- 版本信息管理和启动日志
- 管理员权限自动申请

### 技术债务
- `workspace_tab.py` 需要继续拆分
- 部分 UI 样式散落在业务代码中
- 需要建立性能基线

---

## 版本规划

### 计划中
- [ ] Rule Engine 消费 Skill 结果
- [ ] 规则 explain 字段与 UI 帮助自动同步
- [ ] 规则类型分层（Persistence / Skill / Network / Mixed）
- [ ] Skill 基线清单文件化
- [ ] MCP / 工具链异常特征检测

### 待优化
- [ ] 统一 UI 样式令牌
- [ ] 统一日志策略
- [ ] 建立 UI 性能基线