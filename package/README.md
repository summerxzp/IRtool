# 打包说明（Windows）

目标：生成无需安装 Python 即可运行的最小体积版本。

## 目录结构
- `app/`：打包使用的代码副本（不影响原工程）。
- `build.ps1`：打包脚本（PowerShell）。
- `build.cmd`：一键调用 `build.ps1`。
- `requirements-build.txt`：打包依赖（含 PyInstaller）。
- `dist/`：输出目录（打包后自动生成）。
- `upx/`（可选）：放 `upx.exe` 用于进一步压缩体积。

## 打包步骤
在 Windows 上执行：

```bat
cd /d <本项目>\package
build.cmd
```

默认参数：`-Mode onefile -Preset slim`

可选：
- 生成目录版（启动更快、调试更方便）：

```bat
build.cmd -Mode onedir
```

- 如果 slim 模式报错（缺模块），用安全模式：

```bat
build.cmd -Preset safe
```

## 输出
- `onefile`：`dist\sectool.exe`
- `onedir`：`dist\sectool\sectool.exe`

把 `dist` 里的内容发给用户即可，无需安装 Python。

## 进一步减小体积（可选）
- 下载 UPX，把 `upx.exe` 放到 `package\upx\upx.exe`。
- 再次运行 `build.cmd` 即会自动压缩 EXE 和 DLL。

## 注意事项
- 工具依赖 `tools\autorunsc64.exe` 与 `tools\sigcheck64.exe`，已被打包。
- 程序需要管理员权限，首次运行会触发 UAC 提权提示。
- 如果你修改了原工程代码，请手动同步到 `package\app` 再重新打包。
