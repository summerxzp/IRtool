# CI 自动打包与发布说明

## 概述

项目采用 **CI 构建 + 本地发布** 的混合模式：
- **CI**（GitHub Actions）：自动构建 + GitHub Release 上传
- **本地脚本**：打包 + 双平台上传（GitHub + Gitee），Gitee 因网络原因只能本地传

## 发布流程

### 方式一：本地一键发布（推荐）

使用 `scripts/release.ps1`，一步完成打包 + 双平台上传：

```powershell
# 设置凭据（只需设置一次，或写入系统环境变量）
$env:GITEE_TOKEN = "your-gitee-personal-access-token"

# 完整发布：打包 + GitHub + Gitee
pwsh -NoProfile -File scripts/release.ps1

# 跳过构建，只上传已有产物
pwsh -NoProfile -File scripts/release.ps1 -SkipBuild
```

脚本会自动：
1. 调用 `package/build-with-7z.ps1` 构建 7z SFX 自解压包
2. 将 SFX 包裹为 ZIP（避免浏览器"不安全下载"拦截）
3. 上传 ZIP 到 GitHub Release（通过 `gh` CLI）
4. 上传 ZIP 到 Gitee Release（通过 API，需 `GITEE_TOKEN`）

### 方式二：CI 自动构建 + GitHub Release

推送 tag 触发 CI 自动构建：

```powershell
# 1. 更新 pyproject.toml 中的 version 字段
# 2. 提交并打 tag
git add -A
git commit -m "chore: bump version to x.y.z"
git tag vx.y.z
git push origin main
git push origin vx.y.z
```

CI 构建完成后自动上传到 GitHub Release。Gitee 需手动用本地脚本上传。

### 方式三：手动触发 CI（测试打包）

```
Actions → Build → Run workflow → Run
```

构建产物出现在 Artifacts 区域（保留 7 天），不会上传到 Release。

## 产物命名

| 来源 | 文件名 | 说明 |
|------|--------|------|
| Artifact | `IRtool-vx.y.z.zip` | Actions 页面下载 |
| Release | `IRtool-vx.y.z.zip` | Release 页面下载，内含 SFX 自解压 exe |

用户下载 ZIP 后解压，双击 `IRtool-vx.y.z-7z.exe` 即可运行。

## 凭据配置

| 变量 | 用途 | 配置方式 |
|------|------|----------|
| `GITEE_TOKEN` | Gitee API 鉴权 | 环境变量或 `-GiteeToken` 参数 |
| GitHub | Release 上传 | `gh auth login` 登录即可 |
| CI `GITEE_TOKEN` | 已弃用 | 原 CI Gitee 同步已移除 |

Gitee Token 获取：Gitee → 设置 → 私人令牌 → 生成新令牌（勾选 projects 权限）。

## 配置文件

| 文件 | 用途 |
|------|------|
| `.github/workflows/build.yml` | CI 构建流程定义（仅构建 + GitHub Release） |
| `scripts/release.ps1` | 本地一键发布脚本（打包 + 双平台上传） |
| `package/requirements-build.txt` | 打包依赖（锁定版本） |
| `package/build-with-7z.ps1` | 构建脚本（CI 和本地共用） |
| `package/sfx_config_template.txt` | 7z SFX 配置模板 |
| `package/IRtool.manifest` | UAC 清单 |
| `bak/` | 本地备份目录（git 已忽略） |

## CI 环境配置

| 项目 | 配置 |
|------|------|
| Runner | `windows-latest` |
| Python | 3.11 |
| 7-Zip | 通过 Chocolatey 安装 |
| 打包工具 | PyInstaller 6.3.0 |
| 压缩方式 | 7z LZMA2 极限压缩 + SFX 自解压 + ZIP 外层包裹 |

## 版本号管理

版本号单一来源：`pyproject.toml` 中的 `version` 字段。

CI 和发布脚本均从 `pyproject.toml` 读取版本号，用于：
- 构建脚本生成 `.version` 文件（运行时读取）
- Artifact 和 Release 产物命名
- SFX 自解压配置
- Git tag 命名

## 本地打包 vs CI 打包

| 对比项 | 本地打包 | CI 打包 |
|--------|---------|---------|
| 体积 | ~54 MB | ~55 MB |
| 环境 | 本机 | 干净虚拟机 |
| 可复现性 | 依赖本机环境 | 完全可复现 |
| 操作 | 运行发布脚本 | 推送 tag 或点按钮 |
| Gitee 上传 | ✅ 本地直传快（~15s） | ❌ 跨境超时 |
| 适用场景 | 正式发版 | 自动构建验证 |

## 故障排除

- **构建失败**：在 Actions 页面查看详细日志，定位失败步骤
- **版本号显示 0.0.0**：检查 `.version` 文件是否正确生成（构建脚本自动写入）
- **7z SFX 模块未找到**：CI 环境通过 Chocolatey 安装 7-Zip，`7z.sfx` 位于安装目录下
- **Gitee 上传失败**：检查 `GITEE_TOKEN` 是否有效，是否勾选了 projects 权限
- **浏览器拦截下载**：下载 ZIP 格式而非直接下载 exe，ZIP 不会触发浏览器安全警告
