# 开发维护规范

## 版本号规范

采用 [语义化版本](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`：

| 位 | 含义 | 何时递增 | 示例 |
|----|------|---------|------|
| MAJOR | 不兼容的 API 变更 | 架构重构、功能移除 | 1.x.x → 2.0.0 |
| MINOR | 向后兼容的功能新增 | 新增检测模块、新 UI 功能 | 1.1.x → 1.2.0 |
| PATCH | 向后兼容的问题修复 | bug 修复、文案调整、性能优化 | 1.1.4 → 1.1.5 |

### 版本号单一来源

版本号只在 `pyproject.toml` 中定义，其他位置均动态读取：

```
pyproject.toml          ← 唯一定义处
  ├── core/constants.py   运行时读取（源码环境 / .version 文件 / 环境变量）
  ├── package/build-with-7z.ps1  构建时读取
  └── .github/workflows/build.yml  CI 构建时读取
```

**禁止**在 `constants.py`、构建脚本或其他文件中硬编码版本号。

## 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <subject>
```

### type 类型

| type | 说明 | 是否影响版本 |
|------|------|:---:|
| `feat` | 新功能 | MINOR |
| `fix` | 修复 bug | PATCH |
| `refactor` | 重构（非新功能、非修复） | — |
| `perf` | 性能优化 | PATCH |
| `ui` | UI 调整 | PATCH |
| `docs` | 文档变更 | — |
| `test` | 测试相关 | — |
| `chore` | 构建/工具/依赖 | — |

### scope 范围

`autoruns` `network` `workspace` `rule-engine` `sysmon` `threat-intel` `skill-scan` `ui` `utils` `build` `ci`

### 示例

```
feat(autoruns): 添加进程父进程链查看功能
fix(network): 修复连接状态过滤逻辑
refactor(rule-engine): 提取 IP 匹配为独立方法
perf(autoruns): 优化大列表渲染性能
chore(deps): 更新 PyQt6 到 6.10.2
ci: 修复构建脚本 7z 路径问题
```

### 提交模板

```bash
git config commit.template .gitmessage
```

配置后 `git commit` 会自动加载模板。

## 分支规范

| 分支 | 用途 | 保护 |
|------|------|:---:|
| `main` | 稳定版本，始终可发布 | ✅ |
| `dev` | 开发集成，功能测试 | — |
| `feat/*` | 功能分支，完成后合并回 dev | — |
| `fix/*` | 修复分支，完成后合并回 dev | — |

### 工作流

```
feat/xxx ──→ dev ──→ main (tag vx.y.z)
fix/xxx  ──↗
```

小项目可简化为直接在 `main` 上开发，发版时打 tag。

## 发版流程

### 1. 更新版本号

编辑 `pyproject.toml` 中的 `version` 字段，根据变更类型递增：

- 新功能 → 递增 MINOR（1.1.4 → 1.2.0）
- bug 修复 → 递增 PATCH（1.1.4 → 1.1.5）

### 2. 提交并打 Tag

```bash
git add -A
git commit -m "chore: bump version to x.y.z"
git tag vx.y.z
git push origin main
git push origin vx.y.z
```

推送 tag 后 CI 自动构建并上传到 Release。

### 3. 编写 Release Notes

在 GitHub Release 页面编辑，建议格式：

```markdown
## 新增
- ...

## 修复
- ...

## 优化
- ...
```

### 发版检查清单

- [ ] `pyproject.toml` 版本号已更新
- [ ] 所有测试通过（`pytest tests/`）
- [ ] 源码运行正常
- [ ] CI 构建成功
- [ ] Release Notes 已编写

## 依赖管理

### 三个依赖文件

| 文件 | 用途 | 版本策略 |
|------|------|---------|
| `requirements.txt` | 运行时依赖 | 宽松（`>=`） |
| `requirements-dev.txt` | 开发/测试依赖 | 宽松（`>=`） |
| `package/requirements-build.txt` | 打包依赖 | **锁定**（`==`） |

### 更新依赖

- **运行时依赖**：同时更新 `requirements.txt` 和 `pyproject.toml`
- **打包依赖**：只更新 `package/requirements-build.txt`，锁定版本确保可复现
- **开发依赖**：更新 `requirements-dev.txt` 和 `pyproject.toml` 的 `[project.optional-dependencies.dev]`

## 代码规范

### 分层原则

| 层级 | 职责 | 禁止 |
|------|------|------|
| `ui/` | 编排交互和展示 | 实现业务逻辑 |
| `core/` | 业务逻辑处理 | 依赖 UI 控件 |
| `utils/` | 可复用通用能力 | 放置业务编排逻辑 |

### 日志

```python
import logging
LOGGER = logging.getLogger("IRtool.module_name")

LOGGER.info(f"[Module] 操作完成: {result}")
LOGGER.error(f"[Module] 操作失败: {error}", exc_info=True)
```

禁止使用 `print()` 和 `traceback.print_exc()`。

### 异常处理

```python
# 正确
except Exception:
    pass

# 错误
except:
    pass
```

### 路径适配

所有路径通过 `utils/path_resolver.py` 获取，支持源码运行和 PyInstaller 打包：

```python
from utils.path_resolver import get_app_dir, get_data_dir
```

禁止硬编码路径或自行计算应用根目录。

## 测试规范

### 运行测试

```bash
pytest tests/ -v
```

### 编写测试

- 测试文件放在 `tests/` 目录，命名 `test_*.py`
- PyQt6 和 psutil 由 `tests/conftest.py` mock，测试无需安装 GUI 依赖
- 新功能必须附带测试

### Mock 策略

`conftest.py` 已 mock 以下模块，测试中可直接 import 而不触发 PyQt6：

- `PyQt6` / `PyQt6.QtCore` / `PyQt6.QtGui` / `PyQt6.QtWidgets`
- `psutil`
