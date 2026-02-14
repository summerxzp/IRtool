# IRtool 发布打包指南

## 版本信息

### 当前版本: v1.0.0

**发布日期**: 2026-02-14  
**构建类型**: release  
**构建模式**: onedir-7z (自解压)  

### 版本更新日志

#### v1.0.0 (2026-02-14)
- 首次发布
- 工具名称从 sectool 更名为 IRtool
- 实现 onedir + 7z 自解压打包
- 添加版本信息管理和启动日志
- 支持 PyInstaller 打包后的路径适配

---

## 打包方式

### 1. 环境准备

**必需软件**:
- Python 3.11+
- 7-Zip (用于创建自解压包)
- Windows 系统

**检查 7-Zip 安装**:
```powershell
# 脚本会自动检测以下位置
- C:\Program Files\7-Zip\7z.exe
- C:\Program Files (x86)\7-Zip\7z.exe
- 系统 PATH 中的 7z 命令
```

### 2. 打包脚本

**脚本位置**: `package/build-with-7z.ps1`

**使用方法**:

```powershell
# 默认模式: onedir-7z (推荐)
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1

# 仅构建目录模式
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir

# 显式指定 7z 模式
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir-7z
```

### 3. 构建模式对比

| 模式 | 输出 | 大小 | 适用场景 |
|------|------|------|----------|
| `onedir-7z` (默认) | 单个 .exe 文件 | ~37 MB | 分发、部署 |
| `onedir` | 文件夹 | ~140 MB | 调试、开发 |

### 4. 输出位置

```
package/dist/
├── IRtool-v{版本号}-7z.exe    # onedir-7z 模式输出 (自解压包)
└── IRtool-v{版本号}/          # onedir 模式输出目录
```

**命名规范说明**:
- 自解压包添加 `-7z` 后缀，避免与解压后的主程序同名
- 解压后运行 `IRtool-v{版本号}.exe` (主程序)

---

## 打包规范

### 1. 版本管理

**版本常量定义位置**: `core/constants.py`

```python
APP_NAME = "终端安全检测工具"
APP_ID = "com.internal.IRtool"
APP_VERSION = "1.0.0"        # 更新版本时修改此处
BUILD_TYPE = "release"       # release | dev
BUILD_DATE = "2026-02-14"    # 更新日期
```

**版本同步检查清单**:
- [ ] `core/constants.py` 中的 `APP_VERSION`
- [ ] `package/build-with-7z.ps1` 中的 `$appVersion`
- [ ] `package/build-with-7z.ps1` 中的 `$buildDate`

### 2. 目录结构规范

打包后的应用目录结构:

```
IRtool-v{版本号}/
├── IRtool-v{版本号}.exe    # 主程序
├── _internal/              # PyInstaller 内部目录
│   ├── tools/              # 外部工具
│   │   ├── autorunsc64.exe
│   │   └── sigcheck64.exe
│   ├── data/               # 数据文件
│   │   └── rules.json
│   └── ...                 # 依赖库
├── logs/                   # 日志目录 (运行时创建)
└── config/                 # 配置目录 (运行时创建)
```

### 3. 路径适配规范

**源码运行 vs 打包运行路径差异**:

| 环境 | 工具路径 | 数据路径 |
|------|----------|----------|
| 源码 | `./tools/` | `./data/` |
| 打包 | `./_internal/tools/` | `./_internal/data/` |

**代码实现** (使用 `sys.frozen` 检测):

```python
def get_app_dir() -> Path:
    """获取应用根目录（支持源码运行和PyInstaller打包）"""
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后，使用可执行文件所在目录
        return Path(sys.executable).parent
    else:
        # 源码运行，使用脚本所在目录
        return Path(__file__).parent.parent
```

**需要适配路径的文件**:
- `core/autoruns_parser.py` - autorunsc64.exe 路径
- `ui/autoruns_tab.py` - sigcheck64.exe 路径
- `core/rule_engine.py` - rules.json 路径

### 4. 日志规范

**日志位置**: `{APP_DIR}/logs/IRtool_YYYYMMDD.log`

**启动日志格式**:
```
[Startup] ========================================
[Startup] AppID: com.internal.IRtool
[Startup] Version: 1.0.0
[Startup] Build: release (2026-02-14)
[Startup] App Directory: D:\...\IRtool-v1.0.0
[Startup] ========================================
```

### 5. 管理员权限

**实现方式**: 在 `main.py` 中检测并自动提权

```python
def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新运行程序"""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit(0)
```

**幂等性保证**: 已以管理员模式运行时不会重复申请

### 6. 构建参数规范

**PyInstaller 参数**:
```powershell
--onedir                    # 目录模式 (非单文件)
--noconsole                 # 无控制台窗口
--clean                     # 清理缓存
--manifest                  # 管理员权限清单
--add-data                 # 包含数据和工具
--exclude-module           # 排除不必要模块 (减小体积)
```

**7z 压缩参数**:
```powershell
-t7z                        # 7z 格式
-m0=lzma2                  # LZMA2 压缩算法
-mx=9                       # 最高压缩级别
```

---

## 经验补充

### 1. 常见问题

#### Q: 7z.sfx 模块找不到
**解决**: 确保使用 7-Zip 官方版本，而非精简版。模块位于 `C:\Program Files\7-Zip\7z.sfx`

#### Q: 打包后找不到工具文件
**解决**: 检查路径适配代码是否正确处理 `_internal/` 前缀

#### Q: 自解压后程序无法启动
**解决**: 检查 `sfx_config.txt` 中的 `GUIRunOnce` 路径是否正确

#### Q: 自解压时出现"文件替换"弹窗
**原因**: 打包文件和解压后的主程序同名  
**解决**: 自解压包使用 `-7z` 后缀命名，如 `IRtool-v1.0.0-7z.exe`

### 2. 体积优化技巧

**已排除的模块** (节省 ~50MB):
- matplotlib, numpy, pandas, scipy
- PIL/Pillow
- PyQt6 的多媒体、Web、3D 模块
- unittest, pydoc, pdb 等开发工具

### 3. 调试技巧

**查看打包日志**:
```powershell
# 构建日志
package/build/IRtool-v1.0.0/warn-IRtool-v1.0.0.txt

# 运行时日志
package/dist/IRtool-v1.0.0/logs/IRtool_YYYYMMDD.log
```

**测试打包版本**:
```powershell
# 直接运行目录版本测试
cd package/dist/IRtool-v1.0.0
.\IRtool-v1.0.0.exe
```

### 4. 安全注意事项

- 不要将敏感信息硬编码到代码中
- 使用环境变量存储 API 密钥等敏感信息
- 日志中不要记录敏感数据
- 分发前检查是否包含调试信息

---

## 快速检查清单

发布新版本前确认:

- [ ] 更新 `core/constants.py` 版本号
- [ ] 更新 `package/build-with-7z.ps1` 版本号
- [ ] 更新 `Release.md` 版本日志
- [ ] 测试源码运行正常
- [ ] 测试打包后运行正常
- [ ] 检查日志输出正确
- [ ] 验证管理员权限申请
- [ ] 验证工具调用正常 (autoruns, sigcheck)

---

*本文档由 AI 辅助生成，如有疑问请参考项目 README.md 或联系维护人员。*
