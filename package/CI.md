# CI 自动打包说明

## 概述

项目通过 GitHub Actions 实现自动打包，无需本地安装任何构建工具，浏览器操作即可完成发版。

## 触发方式

### 方式一：推送 Tag（正式发版）

更新版本号后推送 tag，自动触发打包并上传到 GitHub Release。

```powershell
# 1. 更新 pyproject.toml 中的 version 字段
# 2. 提交并打 tag
git add -A
git commit -m "chore: bump version to x.y.z"
git tag vx.y.z
git push origin main
git push origin vx.y.z
```

构建完成后产物自动上传到对应 Release 页面。

### 方式二：手动触发（测试打包）

在 GitHub 仓库页面操作：

```
Actions → Build → Run workflow → Run
```

构建完成后产物出现在 Artifacts 区域（保留 7 天），不会上传到 Release。

## 产物命名

| 来源 | 文件名 | 说明 |
|------|--------|------|
| Artifact | `IRtool-vx.y.z.zip` | Actions 页面下载，内含 exe |
| Release | `IRtool-vx.y.z-7z.exe` | Release 页面下载，自解压包 |

## 配置文件

| 文件 | 用途 |
|------|------|
| `.github/workflows/build.yml` | CI 打包流程定义 |
| `package/requirements-build.txt` | 打包依赖（锁定版本） |
| `package/build-with-7z.ps1` | 构建脚本（CI 和本地共用） |
| `package/sfx_config_template.txt` | 7z SFX 配置模板 |
| `package/IRtool.manifest` | UAC 清单 |

## CI 环境配置

| 项目 | 配置 |
|------|------|
| Runner | `windows-latest` |
| Python | 3.11 |
| 7-Zip | 通过 Chocolatey 安装 |
| 打包工具 | PyInstaller 6.3.0 |
| 压缩方式 | 7z LZMA2 极限压缩 + SFX 自解压 |

## 版本号管理

版本号单一来源：`pyproject.toml` 中的 `version` 字段。

CI 从 `pyproject.toml` 读取版本号，用于：
- 构建脚本生成 `.version` 文件（运行时读取）
- Artifact 和 Release 产物命名
- SFX 自解压配置

## 本地打包 vs CI 打包

| 对比项 | 本地打包 | CI 打包 |
|--------|---------|---------|
| 体积 | ~54 MB | ~55 MB |
| 环境 | 本机 | 干净虚拟机 |
| 可复现性 | 依赖本机环境 | 完全可复现 |
| 操作 | 运行 PowerShell 脚本 | 推送 tag 或点按钮 |
| 适用场景 | 调试构建问题 | 正式发版 |

## 故障排除

- **构建失败**：在 Actions 页面查看详细日志，定位失败步骤
- **版本号显示 0.0.0**：检查 `.version` 文件是否正确生成（构建脚本自动写入）
- **7z SFX 模块未找到**：CI 环境通过 Chocolatey 安装 7-Zip，`7z.sfx` 位于安装目录下
- **Artifact 下载后是 zip**：GitHub Actions 自动将 Artifact 打包为 zip，解压后即为 exe
