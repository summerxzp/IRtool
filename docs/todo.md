# 待完成事项

## 后续优化

### autoruns_tab.py 拆分重构
- **优先级**：P1（延后）
- **当前状态**：1653 行，功能正常但影响可维护性
- **拆分方案**：
  1. `ui/autoruns_context_menu.py` — 右键菜单逻辑
  2. `ui/autoruns_file_ops.py` — 文件操作（加密、导出）
  3. `ui/autoruns_navigation.py` — 跳转逻辑（注册表、任务计划）
  4. 保留 `autoruns_scan_controller.py` 和 `autoruns_detail_renderer.py`

## 版本规划

- [ ] Rule Engine 消费 Skill 结果
- [ ] 规则 explain 字段与 UI 帮助自动同步
- [ ] 规则类型分层（Persistence / Skill / Network / Mixed）
- [ ] Skill 基线清单文件化
- [ ] MCP / 工具链异常特征检测

## 待优化

- [ ] 统一 UI 样式令牌
- [ ] 统一日志策略
- [ ] 建立 UI 性能基线
