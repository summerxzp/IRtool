# IRtool

![Version](https://img.shields.io/badge/version-1.1.7-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-yellow)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4)

面向 Windows 终端应急响应场景的本地桌面工具，帮助分析人员快速发现网络异常、持久化启动项异常，并进行规则化关联排查与处置辅助。

## 功能特性

- **网络监控** - 实时采集网络连接，支持过滤、搜索、终止进程、导出
- **持久化检测** - 调用 Sysinternals Autoruns 扫描自启动项，支持风险提示、签名验证
- **工作台** - 规则扫描引擎，支持 IOC 导入、规则管理、处置命令模板
- **威胁情报** - VirusTotal / 微步在线哈希查询
- **Sysmon 部署** - 一键部署 Sysmon 监控

## 快速开始

### 系统要求

- Windows 10/11
- 管理员权限（推荐）
- Python 3.11+（仅源码运行需要）

### 方式一：直接运行打包版本

前往 [Releases](../../releases) 下载最新版本，双击解压运行。

### 方式二：源码运行

```bash
# 克隆仓库
git clone https://github.com/summerxzp/IRtool.git
cd IRtool

# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

### 方式三：开发模式安装

```bash
pip install -e ".[dev]"
```

## 项目结构

```text
IRtool/
├── main.py              # 应用入口
├── core/                # 核心业务逻辑
│   ├── autoruns_parser.py   # Autoruns 解析器
│   ├── rule_engine.py       # 规则扫描引擎
│   ├── network_monitor.py   # 网络监控
│   ├── data_store.py        # 数据中心
│   ├── icon_provider.py     # 图标提供者
│   └── threat_intel/        # 威胁情报查询
├── ui/                  # 界面层
│   ├── autoruns_tab.py      # 持久化检测页
│   ├── network_tab.py       # 网络监控页
│   ├── workspace_tab.py     # 工作台页
│   └── ui_style.py          # 样式定义
├── utils/               # 工具层
│   ├── path_resolver.py     # 路径适配
│   └── safe_executor.py     # 安全命令执行
├── tools/               # 外部工具 (autorunsc64.exe, sigcheck64.exe)
├── data/                # 规则数据
├── tests/               # 测试
└── package/             # 打包脚本
```

详细架构说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 测试

```bash
pip install pytest
python -m pytest tests/ -v
```

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1
```

详见 [package/README.md](package/README.md)。

## 开发

见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 常见问题

**Q: 启动时提示缺少模块？**
A: 请确认已安装全部依赖：`pip install -r requirements.txt`

**Q: 网络监控页为空？**
A: 需要以管理员权限运行，否则无法获取完整网络连接信息。

**Q: Autoruns 扫描失败？**
A: 确认 `tools/autorunsc64.exe` 存在且未被杀软隔离。

**Q: 如何添加自定义检测规则？**
A: 编辑 `data/rules.json`，参考现有规则格式添加。规则支持 `contains`、`regex`、`equals` 三种匹配类型。

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

[MIT License](LICENSE)
