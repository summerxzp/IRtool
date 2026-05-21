# IRtool 发布指南

## 版本管理

版本号单一来源：`pyproject.toml` 中的 `version` 字段。

`core/constants.py` 和 `package/build-with-7z.ps1` 均从 `pyproject.toml` 动态读取版本号，无需手动同步。

## 发布流程

### 1. 更新版本号

编辑 `pyproject.toml` 中的 `version` 字段。

### 2. 更新日志

在 `CHANGELOG.md` 顶部添加新版本条目。

### 3. 构建发布包

```powershell
powershell -ExecutionPolicy Bypass -File package/build-with-7z.ps1
```

### 4. 打 Git Tag

```bash
git tag v{版本号}
git push origin v{版本号}
```

## 发布检查清单

- [ ] 更新 `pyproject.toml` 版本号
- [ ] 更新 `CHANGELOG.md` 版本日志
- [ ] 测试源码运行正常
- [ ] 测试打包后运行正常
- [ ] 检查日志输出正确
- [ ] 验证管理员权限申请
- [ ] 验证工具调用正常 (autoruns, sigcheck)
- [ ] 打 Git Tag

## 详细打包说明

见 [package/README.md](package/README.md)。

## 版本更新日志

见 [CHANGELOG.md](CHANGELOG.md)。
