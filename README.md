# IRtool

面向 Windows 终端应急响应场景的本地桌面工具，帮助分析人员快速发现网络异常、持久化启动项异常，并进行规则化关联排查与处置辅助。

## 功能特性

- **网络监控** - 实时采集网络连接，支持过滤、搜索、终止进程、导出
- **持久化检测** - 调用 Sysinternals Autoruns 扫描自启动项，支持风险提示、签名验证
- **工作台** - 规则扫描引擎，支持 IOC 导入、规则管理、处置命令模板

## 快速开始

### 系统要求

- Windows 10/11
- 管理员权限（推荐）

### 运行方式

**方式一：直接运行打包版本**

下载 `IRtool-v1.0.1-7z.exe`，双击解压运行。

**方式二：源码运行**

```bash
pip install -r requirements.txt
python main.py
```

## 项目结构

```text
IRtool/
├── main.py              # 应用入口
├── core/                # 核心业务逻辑
│   ├── autoruns_parser.py
│   ├── rule_engine.py
│   └── threat_intel/
├── ui/                  # 界面层
│   ├── autoruns_tab.py
│   ├── network_tab.py
│   └── workspace_tab.py
├── utils/               # 工具层
├── tools/               # 外部工具 (autorunsc64.exe, sigcheck64.exe)
└── data/                # 规则数据
```

详细架构说明见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 开发

见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT License