# 打包说明（Windows）

## 快速开始

### 前置要求
- Windows 操作系统
- Python 3.11+（已加入 PATH）
- 7-Zip（用于 7z 自解压模式）

### 执行打包

```powershell
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1
```

默认使用 `onedir-7z` 模式（推荐，体积最小）。

### 可选模式

```powershell
# onedir + 7z 自解压（推荐，体积最小）
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir-7z

# onedir 模式（目录形式，便于调试）
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir
```

## 输出文件

| 模式 | 输出文件名 | 大小 | 说明 |
|------|-----------|------|------|
| `onedir-7z` | `IRtool-v{版本号}-7z.exe` | ~37MB | **推荐**，自解压运行 |
| `onedir` | `IRtool-v{版本号}/` | ~140MB | 目录形式，便于调试 |

## 版本管理

版本号单一来源：项目根目录 `pyproject.toml` 中的 `version` 字段。

构建脚本和 `constants.py` 均从 `pyproject.toml` 动态读取版本号，无需手动同步。

## 目录结构

```
package/
├── build-with-7z.ps1       # 唯一主构建脚本
├── IRtool.manifest          # UAC 清单（管理员权限）
├── requirements-build.txt   # 打包依赖
├── sfx_config_template.txt  # 7z SFX 配置模板
└── README.md                # 本文件
```

## 构建流程

1. 自动检测系统 Python，在 `package/.venv` 创建虚拟环境
2. 安装 `requirements-build.txt` 中的依赖
3. 从 `pyproject.toml` 读取版本号
4. PyInstaller onedir 模式打包（排除 50+ 未使用模块）
5. 7z LZMA2 极限压缩 + SFX 自解压封装

## 注意事项

1. **工具依赖**：程序依赖 `tools\autorunsc64.exe` 与 `tools\sigcheck64.exe`，已被打包
2. **管理员权限**：程序需要管理员权限运行，首次启动会触发 UAC 提权提示
3. **虚拟环境**：构建脚本会自动在 `package/.venv` 创建虚拟环境，无需手动配置
4. **排除的模块**：为减小体积，打包时排除了 matplotlib、numpy、pandas、PyQt6.Qt3D* 等 50+ 未使用模块

## 故障排除

- 如果打包过程中出现模块缺失警告，检查 `requirements-build.txt` 是否完整
- 如果运行时缺少 DLL，尝试使用 `-Mode onedir` 模式打包
- 如果 7z 模式报错，检查是否已安装 7-Zip
- 如果 Python 未找到，确认 Python 3.11+ 已安装并加入系统 PATH
