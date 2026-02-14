# 打包说明（Windows）

目标：生成无需安装 Python 即可运行的最小体积版本。

## 推荐方案对比

| 方案 | 体积 | 启动速度 | 稳定性 | 适用场景 |
|------|------|----------|--------|----------|
| **onefile** | ~58MB | 慢（需解压） | 中 | 简单分发 |
| **onedir** | ~140MB | 快 | 高 | 固定安装 |
| **onedir + UPX** | ~50-70MB | 快 | 高 | 需安装 UPX |
| **onedir + 7z** | **~37MB** | **快** | **高** | **推荐方案** |

> **推荐使用 `onedir + 7z` 模式**：体积最小（37MB）、启动快、稳定性高、无需额外依赖

## 目录结构
- `app/`：打包使用的代码副本（包含 core/、ui/、utils/、data/、tools/ 等模块）。
- `build-with-7z.ps1`：**推荐打包脚本**（支持 7z 自解压）。
- `build-balanced.ps1`：平衡打包脚本（支持 UPX）。
- `build-minimal.ps1`：极简打包脚本。
- `requirements-build.txt`：打包依赖（含 PyInstaller）。
- `dist/`：输出目录（打包后自动生成）。
- `upx/`（可选）：放 `upx.exe` 用于压缩体积。

## 快速开始（推荐）

### 1. 前置要求
- Windows 操作系统
- 已安装 Python 3.x
- 已安装 7-Zip（用于 7z 自解压模式）
- 确保 `app/` 目录下的代码为最新版本

### 2. 安装 7-Zip（用于推荐模式）

下载地址：https://www.7-zip.org/

安装后脚本会自动检测 7-Zip 位置。

### 3. 执行打包

在 Windows PowerShell 中执行：

```powershell
cd d:\project\sectool_codex\package\package
powershell -ExecutionPolicy Bypass -File build-with-7z.ps1
```

默认使用 `onedir-7z` 模式（推荐）。

### 4. 可选模式

```powershell
# onedir + 7z 自解压（推荐，体积最小~37MB）
powershell -ExecutionPolicy Bypass -File build-with-7z.ps1 -Mode onedir-7z

# onefile 模式（单文件~58MB）
powershell -ExecutionPolicy Bypass -File build-with-7z.ps1 -Mode onefile

# onedir 模式（目录~140MB）
powershell -ExecutionPolicy Bypass -File build-with-7z.ps1 -Mode onedir

# onedir + UPX（需先安装UPX）
powershell -ExecutionPolicy Bypass -File build-with-7z.ps1 -Mode onedir-upx
```

### 5. 输出文件（按打包模式区分）

| 模式 | 输出文件名 | 大小 | 说明 |
|------|-----------|------|------|
| `onedir-7z` | `IRtool-onedir-7z.exe` | ~37MB | **推荐**，自解压运行 |
| `onefile` | `IRtool-onefile.exe` | ~58MB | 单文件 |
| `onedir` | `IRtool-onedir\` | ~140MB | 目录形式 |
| `onedir-upx` | `IRtool-onedir-upx\` | ~50-70MB | UPX压缩目录 |

## 为什么推荐 onedir + 7z？

1. **体积最小**：7z 高压缩率，从 140MB 压缩到 37MB
2. **启动快**：运行时解压到临时目录，然后直接运行（比 onefile 快）
3. **稳定性高**：不会出现 onefile 的临时文件问题
4. **用户体验好**：双击自解压文件，自动解压并运行
5. **无需额外依赖**：用户不需要安装 7-Zip 或 Python

## 打包模式详解

### onedir-7z（推荐）
- **文件名**: `sectool-onedir-7z.exe`
- **体积**: ~37MB
- **原理**: 将 onedir 目录打包成 7z 自解压文件
- **运行**: 双击自动解压到临时目录并运行
- **适用**: 需要小体积+快速启动的场景

### onefile
- **文件名**: `sectool-onefile.exe`
- **体积**: ~58MB
- **原理**: PyInstaller 将所有内容打包到单个 EXE
- **运行**: 每次启动时解压到临时目录
- **适用**: 只需要发送一个文件的场景

### onedir
- **文件夹名**: `IRtool-onedir\`
- **体积**: ~140MB
- **原理**: 生成目录结构，文件不压缩
- **运行**: 直接运行，启动最快
- **适用**: 固定安装、频繁使用的场景

### onedir-upx
- **文件夹名**: `IRtool-onedir-upx\`
- **体积**: ~50-70MB（需 UPX）
- **原理**: onedir + UPX 压缩 EXE/DLL
- **运行**: 直接运行，启动快
- **适用**: 有 UPX 环境，需要平衡体积和性能

## UPX 下载与配置（可选）

1. 访问 https://github.com/upx/upx/releases
2. 下载 Windows 版本（如 `upx-4.2.4-win64.zip`）
3. 解压后将 `upx.exe` 放到 `package\upx\upx.exe`
4. 使用 `-Mode onedir-upx` 打包

## 注意事项

1. **工具依赖**：程序依赖 `tools\autorunsc64.exe` 与 `tools\sigcheck64.exe`，已被打包。

2. **管理员权限**：程序需要管理员权限运行，首次启动会触发 UAC 提权提示。

3. **代码同步**：如果修改了原工程代码，请手动同步到 `package\app` 目录后再重新打包。

4. **虚拟环境**：打包脚本会自动创建 `.venv` 虚拟环境用于构建隔离，无需手动配置。

5. **排除的模块**：为减小体积，打包时排除了以下未使用的模块：
   - Python 标准库：`matplotlib`, `numpy`, `pandas`, `scipy`, `PIL`, `unittest`, `pydoc`, `pdb`, `tkinter` 等
   - PyQt6 模块：`Qt3D*`, `QtBluetooth`, `QtCharts`, `QtMultimedia`, `QtNetworkAuth`, `QtSql`, `QtWebEngine*` 等

6. **分发方式**：
   - `onedir-7z` / `onefile`：直接分发单个 EXE 文件
   - `onedir` / `onedir-upx`：将整个目录压缩后分发

## 故障排除

- 如果打包过程中出现模块缺失警告，检查 `requirements-build.txt` 是否完整
- 如果运行时缺少 DLL，尝试使用 `-Mode onedir` 模式打包
- 如果 7z 模式报错，检查是否已安装 7-Zip
- 查看 `build\IRtool-*\warn-IRtool-*.txt` 了解详细警告信息
