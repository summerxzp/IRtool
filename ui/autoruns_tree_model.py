# ui/autoruns_tree_model.py
"""Autoruns 树形模型模块

包含 TreeNode、AutorunsTreeModel 和 AutorunsFilterProxyModel
"""

# 标准库
import logging
import os
import uuid

# 第三方库
from PyQt6.QtCore import (
    QAbstractItemModel,
    QElapsedTimer,
    QModelIndex,
    Qt,
    QSortFilterProxyModel,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QIcon

# 本地模块
from core.icon_provider import IconProvider
from core.risk_hint import RiskLevel, get_risk_evaluator
from ui.autoruns_entry_mapper import map_to_model_entry
from ui.ui_style import apply_flat_style


LOGGER = logging.getLogger("IRtool.autoruns_tree_model")
DEBUG_LOG_ENABLED = os.getenv("IRTOOL_DEBUG_LOG", "0") == "1"


def _debug_log(msg: str) -> None:
    """调试日志"""
    if DEBUG_LOG_ENABLED:
        LOGGER.debug(msg)


class TreeNode:
    """树节点类，用于真正的父子关系"""

    def __init__(self, data=None, parent=None):
        self.data = data or {}
        self.parent = parent
        self.children = []


class AutorunsTreeModel(QAbstractItemModel):
    """Autoruns 数据的树形模型（基于真正的父子关系）"""

    entry_updated = pyqtSignal(str)  # entry_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_nodes = []  # 存储根节点
        self._nodes_by_id = {}
        self._row_by_id = {}
        self._nodes_by_entry_location = {}
        self._nodes_by_entry = {}
        self._icon_provider = IconProvider()
        self._risk_evaluator = get_risk_evaluator()
        self._risk_cache = {}  # 缓存风险评估结果
        self._risk_foreground_brushes = {
            RiskLevel.HIGH_RISK: QBrush(QColor(139, 0, 0)),   # 深红色
            RiskLevel.SUSPICIOUS: QBrush(QColor(184, 134, 11)),  # 深金色
        }
        self._risk_background_brushes = {
            RiskLevel.HIGH_RISK: QBrush(QColor(255, 245, 245)),  # 更低饱和背景
            RiskLevel.SUSPICIOUS: QBrush(QColor(255, 252, 242)),  # 更低饱和背景
        }
        self._model_perf_threshold_ms = 50

    def _reset_indexes(self) -> None:
        """重置索引"""
        self._nodes_by_id.clear()
        self._row_by_id.clear()
        self._nodes_by_entry_location.clear()
        self._nodes_by_entry.clear()

    def _index_node(self, node, row: int) -> None:
        """索引节点"""
        if not node or not isinstance(node.data, dict):
            return

        entry_id = node.data.get('id')
        if entry_id:
            self._nodes_by_id[entry_id] = node
            self._row_by_id[entry_id] = row

        entry_name = node.data.get('entry', '')
        location = node.data.get('location', '')
        if entry_name:
            self._nodes_by_entry.setdefault(entry_name, []).append(node)
            if location:
                key = (entry_name, location)
                if key not in self._nodes_by_entry_location:
                    self._nodes_by_entry_location[key] = node

    def _deindex_node(self, node) -> None:
        """移除节点索引"""
        if not node or not isinstance(node.data, dict):
            return

        entry_id = node.data.get('id')
        if entry_id:
            self._nodes_by_id.pop(entry_id, None)
            self._row_by_id.pop(entry_id, None)

        entry_name = node.data.get('entry', '')
        location = node.data.get('location', '')
        if entry_name:
            bucket = self._nodes_by_entry.get(entry_name, [])
            if node in bucket:
                bucket.remove(node)
            if not bucket:
                self._nodes_by_entry.pop(entry_name, None)
            if location:
                key = (entry_name, location)
                mapped = self._nodes_by_entry_location.get(key)
                if mapped is node:
                    replacement = None
                    for candidate in bucket:
                        if candidate.data.get('location', '') == location:
                            replacement = candidate
                            break
                    if replacement is not None:
                        self._nodes_by_entry_location[key] = replacement
                    else:
                        self._nodes_by_entry_location.pop(key, None)

    def _rebuild_row_index(self) -> None:
        """重建行索引"""
        self._row_by_id.clear()
        for idx, node in enumerate(self.root_nodes):
            entry_id = node.data.get('id')
            if entry_id:
                self._row_by_id[entry_id] = idx

    def get_node_by_id(self, entry_id: str):
        """通过 ID 获取节点"""
        return self._nodes_by_id.get(entry_id)

    def get_node_by_entry_location(self, entry_name: str, location: str = ""):
        """通过条目名和位置获取节点"""
        if not entry_name:
            return None
        if location:
            node = self._nodes_by_entry_location.get((entry_name, location))
            if node:
                return node
        bucket = self._nodes_by_entry.get(entry_name, [])
        return bucket[0] if bucket else None

    def get_source_index_for_node(self, node):
        """获取节点的源索引"""
        if not node:
            return QModelIndex()
        entry_id = node.data.get('id') if isinstance(node.data, dict) else None
        if entry_id and entry_id in self._row_by_id:
            return self.index(self._row_by_id[entry_id], 0)
        try:
            row = self.root_nodes.index(node)
        except ValueError:
            return QModelIndex()
        return self.index(row, 0)

    def get_source_index_by_id(self, entry_id: str):
        """通过 ID 获取源索引"""
        node = self.get_node_by_id(entry_id)
        if not node:
            return QModelIndex()
        return self.get_source_index_for_node(node)

    def remove_node_by_id(self, entry_id: str) -> bool:
        """通过 ID 移除节点"""
        node = self.get_node_by_id(entry_id)
        if not node:
            return False
        row = self._row_by_id.get(entry_id)
        if row is None:
            try:
                row = self.root_nodes.index(node)
            except ValueError:
                return False

        self.beginRemoveRows(QModelIndex(), row, row)
        removed = self.root_nodes.pop(row)
        self.endRemoveRows()
        self._deindex_node(removed)
        self._rebuild_row_index()
        return True

    def _log_perf_if_slow(self, stage: str, timer: QElapsedTimer,
                          threshold_ms: int = None, extra: str = "") -> None:
        """性能日志"""
        threshold = self._model_perf_threshold_ms if threshold_ms is None else threshold_ms
        elapsed = timer.elapsed()
        if elapsed >= threshold:
            suffix = f" {extra}" if extra else ""
            LOGGER.info(f"[Perf][AutorunsTreeModel.{stage}] {elapsed}ms{suffix}")

    def _compose_publisher_display(self, entry_data: dict) -> str:
        """组合发布者显示文本"""
        publisher = entry_data.get('publisher', '')
        signer_status = entry_data.get('signer_status', '')
        if '(Verified)' in signer_status:
            return f"(Verified) {publisher}"
        if '(Error)' in signer_status:
            error_reason = entry_data.get('signature_detail', 'Unknown error')
            return f"(Error) {error_reason}"
        return "(Unsigned)"

    def _refresh_entry_cache(
        self,
        entry_data: dict,
        invalidate_risk: bool = True,
        precompute_risk: bool = False,
    ) -> None:
        """预计算显示与搜索字段，减少 data()/filter 重复开销"""
        entry_data['_display_values'] = (
            entry_data.get('category', ''),
            entry_data.get('entry', ''),
            entry_data.get('description', ''),
            self._compose_publisher_display(entry_data),
            entry_data.get('image_path', ''),
            entry_data.get('command_line', '') or entry_data.get('launch_string', ''),
        )
        search_fields = [
            entry_data.get('entry', ''),
            entry_data.get('description', ''),
            entry_data.get('publisher', ''),
            entry_data.get('image_path', ''),
            entry_data.get('command_line', '') or entry_data.get('launch_string', ''),
        ]
        entry_data['_search_blob'] = " ".join(str(v) for v in search_fields if v).lower()

        if invalidate_risk or precompute_risk:
            self._ensure_risk_visual_cache(entry_data, invalidate_cache=invalidate_risk)

    def _get_risk_level_for_entry(self, entry_data: dict, invalidate_cache: bool = False):
        """获取条目的风险等级"""
        entry_id = entry_data.get('id', '')
        if invalidate_cache and entry_id:
            self._risk_cache.pop(entry_id, None)

        if entry_id in self._risk_cache:
            return self._risk_cache[entry_id]

        risk_level = self._risk_evaluator.evaluate(entry_data).level
        if entry_id:
            self._risk_cache[entry_id] = risk_level
        return risk_level

    def _ensure_risk_visual_cache(self, entry_data: dict, invalidate_cache: bool = False) -> int:
        """确保风险可视化缓存"""
        previous_risk_level = entry_data.get('_risk_level')
        base_risk_level = self._get_risk_level_for_entry(entry_data, invalidate_cache=invalidate_cache)
        risk_level = self._get_visual_risk_level(entry_data, base_risk_level)
        entry_data['_risk_level'] = risk_level
        entry_data['_fg_brush'] = self._risk_foreground_brushes.get(risk_level)
        entry_data['_bg_brush'] = self._risk_background_brushes.get(risk_level)
        if previous_risk_level is not None and previous_risk_level != risk_level:
            entry_data.pop('_icon_overlay', None)
        return risk_level

    @staticmethod
    def _get_visual_risk_level(entry_data: dict, base_risk_level: int) -> int:
        """根据当前产品要求覆盖视觉风险等级。"""
        signer_status = str(entry_data.get('signer_status', '') or '')
        is_verified = '(Verified)' in signer_status
        file_exists = bool(entry_data.get('file_exists', True))

        # 产品要求：
        # 1. Unsigned 显示红色
        # 2. File not found 显示黄色
        if not file_exists:
            return RiskLevel.SUSPICIOUS
        if not is_verified:
            return RiskLevel.HIGH_RISK
        return base_risk_level

    def refresh_node(self, node) -> None:
        """节点数据更新后刷新缓存"""
        if not node or not isinstance(node.data, dict):
            return
        self._refresh_entry_cache(node.data, invalidate_risk=True)

    def emit_node_changed(self, node) -> None:
        """统一发出节点刷新信号"""
        if not node:
            return
        entry_id = node.data.get('id') if isinstance(node.data, dict) else None
        row = self._row_by_id.get(entry_id) if entry_id else None
        if row is None:
            try:
                row = self.root_nodes.index(node)
            except ValueError:
                return
        if row < 0 or row >= len(self.root_nodes):
            return
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, 4)
        )

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            node = parent.internalPointer()
            return len(node.children)
        else:
            return len(self.root_nodes)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 6

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        node = index.internalPointer()
        if node is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            display_values = node.data.get('_display_values')
            if not display_values:
                self._refresh_entry_cache(node.data, invalidate_risk=False)
                display_values = node.data.get('_display_values', ())
            col = index.column()
            if 0 <= col < len(display_values):
                return display_values[col]
            return None
        elif role == Qt.ItemDataRole.ToolTipRole:
            col = index.column()
            if col == 0:
                return node.data.get('category', '')
            if col == 1:
                return node.data.get('entry', '')
            if col == 2:
                return node.data.get('description', '')
            if col == 3:
                return self._compose_publisher_display(node.data)
            if col == 4:
                return node.data.get('image_path', '')
            if col == 5:
                return node.data.get('command_line', '') or node.data.get('launch_string', '')
            return None
        elif role == Qt.ItemDataRole.DecorationRole:
            # 图标显示：只在 Entry 列（第1列）显示
            if index.column() == 1:
                return self.get_node_icon(node)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._get_row_foreground_color(node, index.column())
        elif role == Qt.ItemDataRole.BackgroundRole:
            return self._get_row_background_color(node, index.column())
        elif role == Qt.ItemDataRole.UserRole:
            return node.data

        return None

    def _get_cached_risk_level(self, node) -> int:
        """获取缓存的风险等级"""
        cached_level = node.data.get('_risk_level')
        if cached_level is not None:
            return cached_level
        return self._ensure_risk_visual_cache(node.data, invalidate_cache=False)

    def get_node_icon(self, node) -> QIcon:
        """获取节点图标（节点级缓存）"""
        cached_icon = node.data.get('_icon_overlay')
        if cached_icon is not None:
            return cached_icon
        image_path = node.data.get('image_path', '')
        risk_level = self._get_cached_risk_level(node)
        icon = self._icon_provider.get_icon_with_overlay(image_path, risk_level)
        node.data['_icon_overlay'] = icon
        return icon

    def _get_row_foreground_color(self, node, column):
        """根据条目状态返回前景颜色（字体颜色）- 使用风险评估"""
        brush = node.data.get('_fg_brush')
        if brush is not None:
            return brush
        self._ensure_risk_visual_cache(node.data, invalidate_cache=False)
        return node.data.get('_fg_brush')

    def _get_row_background_color(self, node, column):
        """根据条目状态返回背景颜色 - 使用风险评估"""
        brush = node.data.get('_bg_brush')
        if brush is not None:
            return brush
        self._ensure_risk_visual_cache(node.data, invalidate_cache=False)
        return node.data.get('_bg_brush')

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            headers = ['Category', 'Entry', 'Description', 'Publisher', 'Image Path', 'Command Line']
            if section < len(headers):
                return headers[section]
        return None

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            # 顶级节点
            if row < len(self.root_nodes):
                return self.createIndex(row, column, self.root_nodes[row])
        else:
            # 子节点
            parent_node = parent.internalPointer()
            if row < len(parent_node.children):
                return self.createIndex(row, column, parent_node.children[row])

        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        node = index.internalPointer()
        parent_node = node.parent

        if parent_node is None:
            return QModelIndex()

        # 找到父节点在其祖父节点中的行号
        if parent_node.parent is None:
            # 父节点是根节点
            row = self.root_nodes.index(parent_node)
        else:
            # 父节点是子节点
            row = parent_node.parent.children.index(parent_node)

        return self.createIndex(row, 0, parent_node)

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        # 不允许编辑
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def add_entries(self, entries) -> None:
        """添加新的条目到模型"""
        if not entries:
            return

        timer = QElapsedTimer()
        timer.start()
        try:
            _debug_log(f"[Model] 开始添加 {len(entries)} 个条目")

            # 为大量数据批量插入做准备
            self.beginResetModel()

            # 清空现有数据
            self.root_nodes.clear()
            self._risk_cache.clear()
            self._reset_indexes()

            # 批量添加数据
            for i, entry in enumerate(entries):
                try:
                    main_data = map_to_model_entry(entry)
                    main_data["id"] = str(uuid.uuid4())
                    self._refresh_entry_cache(main_data, invalidate_risk=False)

                    main_node = TreeNode(main_data)
                    self.root_nodes.append(main_node)
                    self._index_node(main_node, len(self.root_nodes) - 1)
                except Exception as e:
                    import traceback
                    _debug_log(f"[Model] 处理第 {i} 个条目时出错: {e}")
                    _debug_log(f"[Model] 错误堆栈:\n{traceback.format_exc()}")
                    continue

            # 结束重置
            self.endResetModel()
            _debug_log(f"[Model] 添加条目完成，共 {len(self.root_nodes)} 个条目")
            self._log_perf_if_slow(
                "add_entries",
                timer,
                threshold_ms=50,
                extra=f"entries={len(entries)}",
            )

        except Exception as e:
            import traceback
            _debug_log(f"[Model] 添加条目时发生严重错误: {e}")
            _debug_log(f"[Model] 错误堆栈:\n{traceback.format_exc()}")
            # 确保调用 endResetModel
            try:
                self.endResetModel()
            except:
                pass
            self._log_perf_if_slow(
                "add_entries_failed",
                timer,
                threshold_ms=50,
                extra=f"entries={len(entries)}",
            )

    def clear(self) -> None:
        """清空模型"""
        if self.root_nodes:
            self.beginRemoveRows(QModelIndex(), 0, len(self.root_nodes) - 1)
            self.root_nodes.clear()
            self.endRemoveRows()
        # 清除风险缓存
        self._risk_cache.clear()
        self._reset_indexes()


class AutorunsFilterProxyModel(QSortFilterProxyModel):
    """自定义过滤代理模型，确保Level-1行不参与过滤"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.selected_category = "全部类别"
        self.show_suspicious_only = False

    def apply_filters(self, search_text: str, selected_category: str,
                      show_suspicious_only: bool) -> bool:
        """批量更新过滤条件，仅在变更时触发一次过滤刷新。"""
        normalized_search = (search_text or "").lower()
        normalized_category = selected_category or "全部类别"
        normalized_suspicious_only = bool(show_suspicious_only)
        changed = (
            self.search_text != normalized_search
            or self.selected_category != normalized_category
            or self.show_suspicious_only != normalized_suspicious_only
        )
        if not changed:
            return False
        self.search_text = normalized_search
        self.selected_category = normalized_category
        self.show_suspicious_only = normalized_suspicious_only
        self.invalidateFilter()
        return True

    def set_search_text(self, text) -> None:
        """设置搜索文本"""
        self.apply_filters(text, self.selected_category, self.show_suspicious_only)

    def set_selected_category(self, category) -> None:
        """设置选中的类别"""
        self.apply_filters(self.search_text, category, self.show_suspicious_only)

    def set_show_suspicious_only(self, show_only) -> None:
        """设置是否仅显示可疑项"""
        self.apply_filters(self.search_text, self.selected_category, show_only)

    def _is_suspicious(self, node) -> bool:
        """检测是否为可疑项 - 使用风险评估"""
        # 从源模型获取风险等级
        source_model = self.sourceModel()
        if hasattr(source_model, '_get_cached_risk_level'):
            risk_level = source_model._get_cached_risk_level(node)
            return risk_level >= RiskLevel.SUSPICIOUS

        # 降级方案：使用原有逻辑
        data = node.data
        signer_status = data.get('signer_status', '')
        is_verified = '(Verified)' in signer_status
        if not is_verified:
            return True
        if not data.get('file_exists', True):
            return True
        return False

    def data(self, proxy_index, role=Qt.ItemDataRole.DisplayRole):
        """使用 Qt 默认代理数据路径，避免 Python 层重复转发开销"""
        return super().data(proxy_index, role)

    def filterAcceptsRow(self, source_row, source_parent) -> bool:
        """确定是否接受某一行"""
        # 获取源模型
        source_model = self.sourceModel()

        # 获取当前行的索引
        index = source_model.index(source_row, 0, source_parent)

        # 获取节点数据
        node = index.internalPointer()
        if node is None:
            return True

        # 应用过滤规则
        # 检查搜索条件
        search_match = True
        if self.search_text:
            search_blob = node.data.get('_search_blob', '')
            if not search_blob:
                search_fields = [
                    node.data.get('entry', ''),
                    node.data.get('description', ''),
                    node.data.get('publisher', ''),
                    node.data.get('image_path', ''),
                    node.data.get('command_line', '') or node.data.get('launch_string', '')
                ]
                search_blob = " ".join(str(v) for v in search_fields if v).lower()
                node.data['_search_blob'] = search_blob
            search_match = self.search_text in search_blob

        # 检查类别过滤
        category_match = True
        if self.selected_category != "全部类别":
            category_match = node.data.get('category', '') == self.selected_category

        # 检查可疑项过滤
        suspicious_match = True
        if self.show_suspicious_only:
            suspicious_match = self._is_suspicious(node)

        return search_match and category_match and suspicious_match


__all__ = [
    'TreeNode',
    'AutorunsTreeModel',
    'AutorunsFilterProxyModel',
]
