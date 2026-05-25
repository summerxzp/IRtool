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
# onedir + 7z 自解压 + ZIP 外层包裹（推荐）
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir-7z

# onedir 模式（目录形式，便于调试）
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1 -Mode onedir
```

## 输出文件

| 模式 | 输出文件名 | 说明 |
|------|-----------|------|
| `onedir-7z` | `IRtool-v{版本号}.zip` | **推荐**，ZIP 包裹 SFX 自解压，避免浏览器拦截下载 |
| `onedir-7z` | `IRtool-v{版本号}-7z.exe` | SFX 自解压包（ZIP 内部文件） |
| `onedir` | `IRtool-v{版本号}/` | 目录形式，便于调试 |

用户下载 ZIP 后解压，双击 `IRtool-v{版本号}-7z.exe` 即可运行。

## 版本管理

版本号单一来源：项目根目录 `pyproject.toml` 中的 `version` 字段。

构建脚本和 `constants.py` 均从 `pyproject.toml` 动态读取版本号，无需手动同步。

发版时需同步更新：
1. `pyproject.toml` → `version` 字段
2. `README.md` → 版本徽章
3. `core/constants.py` → `BUILD_DATE` 字段

## 目录结构

```
package/
├── build-with-7z.ps1       # 主构建脚本
├── IRtool.manifest          # UAC 清单（管理员权限）
├── requirements-build.txt   # 打包依赖（锁定版本）
├── sfx_config_template.txt  # 7z SFX 配置模板
├── CI.md                    # CI 与发布流程说明
└── README.md                # 本文件
```

## 构建流程

1. 自动检测系统 Python，在 `package/.venv` 创建虚拟环境
2. 安装 `requirements-build.txt` 中的依赖（锁定版本）
3. 从 `pyproject.toml` 读取版本号
4. 预生成 SVG 图标文件到 `ui/` 目录
5. PyInstaller onedir 模式打包（排除 50+ 未使用模块）
6. 7z LZMA2 极限压缩 + SFX 自解压封装
7. ZIP 外层包裹（避免浏览器"不安全下载"拦截）

## 打包规范

### 依赖版本管理

`requirements-build.txt` 中的依赖版本**必须与项目根目录虚拟环境一致**。

检查方法：
```powershell
# 项目虚拟环境当前版本
E:\Code\IRtool\.venv\Scripts\pip.exe list --format=freeze

# 对比 requirements-build.txt 中的版本
cat package/requirements-build.txt
```

**关键规则**：
- 所有依赖使用 `==` 精确版本锁定，不使用 `>=`
- `PyQt6.QtSvg` 不是独立 pip 包，不要写入 `requirements-build.txt`（它是 PyQt6 的子模块，PyInstaller 通过 `--hidden-import` 自动检测）
- 更新项目依赖后，必须同步更新 `requirements-build.txt`、`requirements.txt`、`pyproject.toml` 三处

### SVG 图标打包

项目使用运行时动态生成 SVG 文件的方式（`ui/ui_style.py` 中的 `ensure_*_svg()` 函数）。

打包时需要：
1. **预生成**：构建脚本在 PyInstaller 执行前调用 `ensure_*_svg()` 生成 SVG 到 `ui/` 目录
2. **打包包含**：通过 `--add-data "ui\_*.svg;ui"` 将 SVG 文件包含到打包产物
3. **运行时查找**：打包模式下（`sys.frozen`），`_ensure_svg()` 从 `_MEIPASS/ui/` 目录查找

新增 SVG 图标时需同步：
1. `ui/ui_style.py`：添加 `_XXX_SVG_CONTENT` 常量和 `ensure_xxx_svg()` 函数
2. `package/build-with-7z.ps1`：添加 `--add-data` 条目和预生成调用
3. `.gitignore`：`ui/_*.svg` 已统一排除（运行时生成，不纳入版本控制）

### QtSvg 依赖

项目使用 `QSvgRenderer` 渲染 SVG 图标（`ui/ui_style.py` 中的 `_render_check_pixmap()`）。

**禁止排除** `PyQt6.QtSvg` 和 `PyQt6.QtSvgWidgets`，否则打包后 SVG 渲染会失败。

构建脚本通过 `--hidden-import PyQt6.QtSvg` 确保 QtSvg 被包含。

### Hidden Imports

以下模块需要 `--hidden-import`（PyInstaller 无法自动检测）：

| 模块 | 原因 |
|------|------|
| `PyQt6.sip` | PyQt6 C 绑定层 |
| `PyQt6.QtSvg` | SVG 渲染（代码中动态使用） |
| `core.sysmon.*` | 通过 `__init__.py` 间接导入 |
| `win32service*` | pywin32 服务管理 |
| `win32evtlog` | Windows 事件日志 |
| `win32api/con/security` | pywin32 工具函数 |

### 排除模块

为减小打包体积，排除 50+ 未使用的 PyQt6 子模块和 Python 标准库模块。

**排除原则**：
- 只排除确认未使用的模块
- 排除前确认代码中无直接或间接引用
- `PyQt6.QtSvg` / `PyQt6.QtSvgWidgets` **不可排除**（见上文）

## 注意事项

1. **工具依赖**：程序依赖 `tools\autorunsc64.exe`、`tools\sigcheck64.exe`、`tools\Sysmon64.exe`，已被打包
2. **管理员权限**：程序需要管理员权限运行，首次启动会触发 UAC 提权提示
3. **虚拟环境**：构建脚本会自动在 `package/.venv` 创建虚拟环境，无需手动配置
4. **排除的模块**：为减小体积，打包时排除了 matplotlib、numpy、pandas、PyQt6.Qt3D* 等 50+ 未使用模块
5. **打包虚拟环境**：如需重建，删除 `package/.venv` 目录后重新运行构建脚本

## 故障排除

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `PyQt6.QtSvg==x.x.x` 安装失败 | `PyQt6.QtSvg` 不是独立 pip 包 | 从 `requirements-build.txt` 移除，改用 `--hidden-import` |
| SVG 预生成 `ModuleNotFoundError: No module named 'ui'` | 打包虚拟环境无项目模块 | 构建脚本已设置 `$env:PYTHONPATH = $appDir` |
| 打包后 check 图标不显示 | `PyQt6.QtSvg` 被排除 | 移除 `--exclude-module PyQt6.QtSvg`，添加 `--hidden-import PyQt6.QtSvg` |
| 打包后 SVG 图标缺失 | 新增 SVG 未添加 `--add-data` | 在构建脚本中添加对应 `--add-data` 条目 |
| 依赖版本不一致 | `requirements-build.txt` 未同步 | 与项目虚拟环境版本对齐，使用 `==` 锁定 |
| 运行时缺少 DLL | 模块被错误排除 | 使用 `-Mode onedir` 调试，检查排除列表 |
| 7z 模式报错 | 未安装 7-Zip | 安装 7-Zip 或使用 `-Mode onedir` |
| Python 未找到 | Python 未加入 PATH | 安装 Python 3.11+ 并加入系统 PATH |
