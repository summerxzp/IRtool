# ui/autoruns_tab.py
import csv
import logging
import locale
import os
import subprocess
import uuid
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QAbstractItemView,
    QCheckBox, QComboBox, QLineEdit, QPushButton, QMessageBox,
    QLabel, QFrame, QSplitter, QTextEdit, QGridLayout, QScrollArea,
    QDialog, QDialogButtonBox, QFileDialog
)
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, pyqtSignal, QSortFilterProxyModel, QTimer, QElapsedTimer, QThread
from PyQt6.QtGui import QColor, QPalette, QIcon, QBrush
from core.icon_provider import IconProvider
from core.risk_hint import get_risk_evaluator, RiskLevel
from core.signature_parser import parse_sigcheck_output, decode_sigcheck_bytes
from ui.autoruns_entry_mapper import map_to_model_entry
from ui.autoruns_detail_renderer import AutorunsDetailRenderer
from ui.autoruns_scan_controller import AutorunsScanController
from ui.ui_style import (
    apply_flat_style,
    AUTORUNS_CONTROL_HEIGHT,
    AUTORUNS_HEADER_HEIGHT,
    AUTORUNS_CATEGORY_WIDTH,
    AUTORUNS_ENTRY_MAX_WIDTH,
    AUTORUNS_DESC_MAX_WIDTH,
    AUTORUNS_PUBLISHER_MAX_WIDTH,
    AUTORUNS_TREE_STYLESHEET,
    AUTORUNS_DETAIL_TITLE_STYLESHEET,
    AUTORUNS_DETAIL_PLACEHOLDER_STYLESHEET,
    AUTORUNS_SCROLL_AREA_STYLESHEET,
    AUTORUNS_HELP_BUTTON_STYLESHEET,
    AUTORUNS_RISK_HELP_TEXT_STYLESHEET,
)


LOGGER = logging.getLogger("sectool.autoruns_tab")
DEBUG_LOG_ENABLED = os.getenv("SECTOOL_DEBUG_LOG", "0") == "1"


def _debug_log(msg: str):
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

    def _reset_indexes(self):
        self._nodes_by_id.clear()
        self._row_by_id.clear()
        self._nodes_by_entry_location.clear()
        self._nodes_by_entry.clear()

    def _index_node(self, node, row: int):
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

    def _deindex_node(self, node):
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

    def _rebuild_row_index(self):
        self._row_by_id.clear()
        for idx, node in enumerate(self.root_nodes):
            entry_id = node.data.get('id')
            if entry_id:
                self._row_by_id[entry_id] = idx

    def get_node_by_id(self, entry_id: str):
        return self._nodes_by_id.get(entry_id)

    def get_node_by_entry_location(self, entry_name: str, location: str = ""):
        if not entry_name:
            return None
        if location:
            node = self._nodes_by_entry_location.get((entry_name, location))
            if node:
                return node
        bucket = self._nodes_by_entry.get(entry_name, [])
        return bucket[0] if bucket else None

    def get_source_index_for_node(self, node):
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
        node = self.get_node_by_id(entry_id)
        if not node:
            return QModelIndex()
        return self.get_source_index_for_node(node)

    def remove_node_by_id(self, entry_id: str) -> bool:
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

    def _log_perf_if_slow(self, stage: str, timer: QElapsedTimer, threshold_ms: int = None, extra: str = ""):
        threshold = self._model_perf_threshold_ms if threshold_ms is None else threshold_ms
        elapsed = timer.elapsed()
        if elapsed >= threshold:
            suffix = f" {extra}" if extra else ""
            LOGGER.info(f"[Perf][AutorunsTreeModel.{stage}] {elapsed}ms{suffix}")

    def _compose_publisher_display(self, entry_data: dict) -> str:
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
    ):
        """预计算显示与搜索字段，减少 data()/filter 重复开销"""
        entry_data['_display_values'] = (
            entry_data.get('category', ''),
            entry_data.get('entry', ''),
            entry_data.get('description', ''),
            self._compose_publisher_display(entry_data),
            entry_data.get('image_path', ''),
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
        previous_risk_level = entry_data.get('_risk_level')
        risk_level = self._get_risk_level_for_entry(entry_data, invalidate_cache=invalidate_cache)
        entry_data['_risk_level'] = risk_level
        entry_data['_fg_brush'] = self._risk_foreground_brushes.get(risk_level)
        entry_data['_bg_brush'] = self._risk_background_brushes.get(risk_level)
        if previous_risk_level is not None and previous_risk_level != risk_level:
            entry_data.pop('_icon_overlay', None)
        return risk_level

    def refresh_node(self, node):
        """节点数据更新后刷新缓存"""
        if not node or not isinstance(node.data, dict):
            return
        self._refresh_entry_cache(node.data, invalidate_risk=True)

    def emit_node_changed(self, node):
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
    
    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            node = parent.internalPointer()
            return len(node.children)
        else:
            return len(self.root_nodes)
    
    def columnCount(self, parent=QModelIndex()):
        return 5  # Category, Entry, Description, Publisher, Image Path
    
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
        # 只对 Entry 列（第 1 列）应用颜色
        if column != 1:
            return None
        brush = node.data.get('_fg_brush')
        if brush is not None:
            return brush
        self._ensure_risk_visual_cache(node.data, invalidate_cache=False)
        return node.data.get('_fg_brush')

    def _get_row_background_color(self, node, column):
        """根据条目状态返回背景颜色 - 使用风险评估"""
        if column != 1:
            return None
        brush = node.data.get('_bg_brush')
        if brush is not None:
            return brush
        self._ensure_risk_visual_cache(node.data, invalidate_cache=False)
        return node.data.get('_bg_brush')

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            headers = ['Category', 'Entry', 'Description', 'Publisher', 'Image Path']
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
    
    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        # 不允许编辑
        return False
    
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    
    def add_entries(self, entries):
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
    
    def clear(self):
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

    def apply_filters(self, search_text: str, selected_category: str, show_suspicious_only: bool) -> bool:
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
    
    def set_search_text(self, text):
        """设置搜索文本"""
        self.apply_filters(text, self.selected_category, self.show_suspicious_only)
    
    def set_selected_category(self, category):
        """设置选中的类别"""
        self.apply_filters(self.search_text, category, self.show_suspicious_only)
    
    def set_show_suspicious_only(self, show_only):
        """设置是否仅显示可疑项"""
        self.apply_filters(self.search_text, self.selected_category, show_only)
    
    def _is_suspicious(self, node):
        """检测是否为可疑项 - 使用风险评估"""
        from core.risk_hint import RiskLevel

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
    
    def filterAcceptsRow(self, source_row, source_parent):
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


class SignatureVerifyWorker(QThread):
    """签名验证线程，避免阻塞 UI"""

    succeeded = pyqtSignal(object)  # payload dict
    failed = pyqtSignal(object)  # payload dict

    def __init__(self, entry_id: str, image_path: str, sigcheck_path: str, encoding: str):
        super().__init__()
        self.entry_id = entry_id
        self.image_path = image_path
        self.sigcheck_path = sigcheck_path
        self.encoding = encoding

    def run(self):
        cmd = [self.sigcheck_path, '-accepteula', '-nobanner', self.image_path]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            stdout = decode_sigcheck_bytes(result.stdout, preferred_encoding=self.encoding)
            stderr = decode_sigcheck_bytes(result.stderr, preferred_encoding=self.encoding)
            if result.returncode == 0:
                self.succeeded.emit(
                    {
                        "entry_id": self.entry_id,
                        "image_path": self.image_path,
                        "output": stdout.strip(),
                    }
                )
                return
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": stderr.strip() or "Unknown error",
                    "severity": "warning",
                }
            )
        except subprocess.TimeoutExpired:
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": "签名验证超时",
                    "severity": "critical",
                }
            )
        except Exception as exc:
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": str(exc),
                    "severity": "critical",
                }
            )


class AutorunsTab(QWidget):
    """持久化检测标签页"""
    
    search_in_workspace = pyqtSignal(str)  # 在工作台搜索信号
    
    @staticmethod
    def format_file_size(size):
        """
        将文件大小格式化为 KB / MB / GB
        支持 int / str / None
        """
        if not size:
            return ""
        
        try:
            # 如果是字符串，尝试转成 int
            size = int(size)
        except (ValueError, TypeError):
            # 如果 autorunsc 给的是 "1,234,567"
            try:
                size = int(str(size).replace(",", ""))
            except Exception:
                return str(size)
        
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
            size /= 1024
        
        return f"{size:.1f} PB"
    
    def __init__(self, autoruns_parser, data_store=None):
        super().__init__()
        apply_flat_style(self)
        self.parser = autoruns_parser
        self.data_store = data_store
        self.current_data = []
        self._icon_warmup_active = False
        self._icon_warmup_index = 0
        self._icon_warmup_batch_size = 20
        self._icon_warmup_interval_ms = 8
        self._filter_debounce_timer = QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.setInterval(150)
        self._filter_debounce_timer.timeout.connect(self._filter_table)
        self._detail_refresh_scheduled = False
        self._pending_detail_data = None
        self._perf_threshold_filter_ms = 16
        self._perf_threshold_detail_ms = 16
        self._perf_threshold_model_ms = 50
        self._column_widths_initialized = False
        self._signature_workers = set()
        self._signature_workers_by_entry_id = {}

        self.scan_controller = AutorunsScanController(self.parser, parent=self)
        self.scan_controller.scan_started.connect(self._on_scan_started)
        self.scan_controller.scan_progress.connect(self._on_scan_progress)
        self.scan_controller.scan_finished.connect(self._on_scan_finished)
        self.scan_controller.scan_error.connect(self._on_scan_error)
        self.scan_controller.scan_cancelled.connect(self._on_scan_cancelled)
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.btn_scan = QPushButton("开始扫描")
        self.btn_scan.clicked.connect(self._start_scan)
        self.btn_scan.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        self.btn_cancel = QPushButton("取消扫描")
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_cancel.setEnabled(False)  # 默认禁用，扫描时启用
        self.btn_cancel.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        self.chk_hash = QCheckBox("计算Hash")
        self.chk_hash.setChecked(False)  # 默认不计算，加快速度

        
        self.chk_sig = QCheckBox("验证签名")
        self.chk_sig.setChecked(False)  # Default to disabled
        
        self.cmb_category = QComboBox()
        self.cmb_category.addItem("全部类别")
        self.cmb_category.currentTextChanged.connect(self._on_category_filter_changed)
        self.cmb_category.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        self.chk_suspicious = QCheckBox("仅显示可疑项")
        self.chk_suspicious.stateChanged.connect(self._on_filter_option_changed)
        
        # 添加搜索框
        search_label = QLabel("搜索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("类型/名称/描述/发布者/文件路径/启动命令")
        self.search_box.textChanged.connect(self._schedule_filter_table)
        self.search_box.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        self.btn_delete = QPushButton("删除选中项")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        self.btn_export = QPushButton("导出CSV")
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)
        
        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_cancel)
        toolbar.addWidget(self.chk_hash)
        toolbar.addWidget(self.chk_sig)
        toolbar.addWidget(self.cmb_category)
        toolbar.addWidget(self.chk_suspicious)
        toolbar.addSpacing(10)
        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_box, 1)  # 1表示拉伸因子
        toolbar.addStretch()
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_export)
        
        layout.addLayout(toolbar)
        
        # 创建垂直分割器
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 主列表区域
        self.tree_view = QTreeView()
        self.model = AutorunsTreeModel()
        
        # 创建自定义过滤代理模型
        self.proxy_model = AutorunsFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Search all columns
        
        # Apply proxy model to tree view
        self.tree_view.setModel(self.proxy_model)
        
        # 监听模型重置信号，仅在重置后调整列宽
        self.model.modelReset.connect(self._on_model_reset)
        
        # 设置选择行为
        self.tree_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tree_view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        
        # 设置根节点不显示装饰箭头
        self.tree_view.setRootIsDecorated(False)

        # 性能优化：列表行高一致时可显著降低大数据滚动开销
        self.tree_view.setUniformRowHeights(True)
        
        # 设置交替行颜色
        self.tree_view.setAlternatingRowColors(False)
        
        # 设置样式：显示行分隔线（不覆盖 Model 的 BackgroundRole）
        self.tree_view.setStyleSheet(AUTORUNS_TREE_STYLESHEET)
        self.tree_view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.tree_view.header().setFixedHeight(AUTORUNS_HEADER_HEIGHT)
        
        # 设置选中态的 palette
        palette = self.tree_view.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        self.tree_view.setPalette(palette)
        
        # 连接选择变化事件
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        # 启用右键菜单
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        
        # 将主列表添加到分割器
        self.splitter.addWidget(self.tree_view)
        
        # Detail Pane 区域
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        
        # Detail 标题
        detail_label = QLabel("详细信息")
        detail_label.setStyleSheet(AUTORUNS_DETAIL_TITLE_STYLESHEET)
        detail_layout.addWidget(detail_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(AUTORUNS_SCROLL_AREA_STYLESHEET)
        
        # Detail 内容容器
        self.detail_widget = QWidget()
        self.detail_layout = QGridLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(10, 10, 10, 10)
        self.detail_layout.setHorizontalSpacing(8)
        self.detail_layout.setVerticalSpacing(2)
        self._detail_renderer = AutorunsDetailRenderer(
            splitter=self.splitter,
            detail_layout=self.detail_layout,
            placeholder_style=AUTORUNS_DETAIL_PLACEHOLDER_STYLESHEET,
        )
        self._detail_renderer.show_placeholder()
        
        scroll_area.setWidget(self.detail_widget)
        detail_layout.addWidget(scroll_area)
        
        # 将 Detail Pane 添加到分割器
        self.splitter.addWidget(detail_container)
        
        # 连接 entry_updated 信号
        self.model.entry_updated.connect(self._on_entry_updated)
        
        # 设置分割器初始比例（主列表占 100%，Detail Pane 默认隐藏）
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1000, 0])
        
        # 将分割器添加到主布局
        layout.addWidget(self.splitter)
        
        # 底部状态栏
        status_layout = QHBoxLayout()
        
        # 创建状态框架
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.Shape.Box)
        self.status_frame.setObjectName("panel")
        # 设置较小的高度，只比字体高一点点
        font_metrics = self.fontMetrics()
        text_height = font_metrics.height()
        self.status_frame.setFixedHeight(text_height + 20)  # 比字体高一点点
        status_inner_layout = QHBoxLayout()
        
        # 状态信息标签
        self.lbl_scan_status = QLabel("就绪")
        self.lbl_scan_duration = QLabel("耗时: 0秒")
        self.lbl_total_items = QLabel("条目: 0")
        self.lbl_categories = QLabel("类别: 0")
        
        status_inner_layout.addWidget(self.lbl_scan_status)
        status_inner_layout.addWidget(self.lbl_scan_duration)
        status_inner_layout.addWidget(self.lbl_total_items)
        status_inner_layout.addWidget(self.lbl_categories)
        status_inner_layout.addStretch()  # 添加伸缩空间，使标签靠左对齐
        
        # 添加帮助按钮
        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(22, 22)
        self.btn_help.setToolTip("风险等级说明")
        self.btn_help.clicked.connect(self._show_risk_help)
        self.btn_help.setStyleSheet(AUTORUNS_HELP_BUTTON_STYLESHEET)
        status_inner_layout.addWidget(self.btn_help)
        
        self.status_frame.setLayout(status_inner_layout)
        layout.addWidget(self.status_frame)

    def _log_perf_if_slow(self, stage: str, timer: QElapsedTimer, threshold_ms: int, extra: str = ""):
        elapsed = timer.elapsed()
        if elapsed >= threshold_ms:
            suffix = f" {extra}" if extra else ""
            LOGGER.info(f"[Perf][AutorunsTab.{stage}] {elapsed}ms{suffix}")

    def _schedule_icon_warmup(self):
        """分批预热图标缓存，减少滚动到新区域时的顿挫"""
        self._icon_warmup_active = True
        self._icon_warmup_index = 0
        QTimer.singleShot(self._icon_warmup_interval_ms, self._warmup_icons_batch)

    def _warmup_icons_batch(self):
        if not self._icon_warmup_active:
            return

        timer = QElapsedTimer()
        timer.start()
        total = len(self.model.root_nodes)
        if self._icon_warmup_index >= total:
            self._icon_warmup_active = False
            return

        start = self._icon_warmup_index
        end = min(start + self._icon_warmup_batch_size, total)
        for i in range(start, end):
            node = self.model.root_nodes[i]
            if not node:
                continue
            self.model.get_node_icon(node)

        self._icon_warmup_index = end
        self._log_perf_if_slow(
            "icon_warmup_batch",
            timer,
            self._perf_threshold_filter_ms,
            extra=f"range={start}-{end}/{total}",
        )
        if self._icon_warmup_index < total and self._icon_warmup_active:
            QTimer.singleShot(self._icon_warmup_interval_ms, self._warmup_icons_batch)
        else:
            self._icon_warmup_active = False
    
    def _start_scan(self):
        """开始扫描"""
        if self.scan_controller.is_scanning:
            return

        self._icon_warmup_active = False

        if self.chk_sig.isChecked():
            reply = QMessageBox.question(
                self, "确认签名验证",
                "验证签名功能需重新扫描，且扫描时间较长(18分钟左右)，是否继续？\n\n注意：此操作可能需要较长时间。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        category_filter = None
        if self.cmb_category.currentIndex() > 0:
            category_filter = [self.cmb_category.currentText()]

        self.scan_controller.start_scan(
            include_hash=self.chk_hash.isChecked(),
            verify_sig=self.chk_sig.isChecked(),
            category_filter=category_filter,
        )

    def _on_scan_started(self):
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("扫描中...")
        self.btn_cancel.setEnabled(True)
        self.lbl_scan_status.setText("扫描中...")
        self.lbl_scan_duration.setText("耗时: 0秒")
        self.lbl_total_items.setText("条目: 0")
        self.lbl_categories.setText("类别: 0")

    def _on_scan_progress(self, message, elapsed):
        """扫描进度更新"""
        self.btn_scan.setText(message)
        self.lbl_scan_status.setText(message)
        self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
    
    def _cancel_scan(self):
        """取消扫描"""
        self._icon_warmup_active = False
        self.scan_controller.cancel_scan()

    def _on_scan_cancelled(self, elapsed):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)
        self.lbl_scan_status.setText("已取消")
        self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
    
    def _on_scan_finished(self, data, elapsed):
        """扫描完成处理"""
        _debug_log(f"[AutorunsTab] 扫描完成，收到 {len(data)} 个条目")
        
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)
        
        self.lbl_scan_status.setText("扫描完成")
        self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
        
        self.current_data = data
        if self.data_store:
            self.data_store.set_autoruns_entries(self.current_data)
        self._update_stats()
        
        self._update_category_filter(data)
        
        _debug_log("[AutorunsTab] 开始填充树形视图")
        self._populate_tree(data)
        _debug_log("[AutorunsTab] 树形视图填充完成")
        self._schedule_icon_warmup()
    
    def _update_stats(self):
        """更新统计信息"""
        self.lbl_total_items.setText(f"条目: {len(self.current_data)}")
        
        # 统计各分类数量
        categories = {}
        for entry in self.current_data:
            # entry 可能是字典或 AutorunEntry 对象
            if hasattr(entry, 'category'):  # 如果是 AutorunEntry 对象
                category = entry.category
            else:  # 如果是字典
                category = entry.get('category', 'Unknown')
            categories[category] = categories.get(category, 0) + 1
        
        self.lbl_categories.setText(f"类别: {len(categories)}")
    
    def _update_category_filter(self, data):
        """Update category filter combo box with unique categories from data"""
        # Get unique categories from the data - handle both dict and AutorunEntry objects
        categories = set()
        for entry in data:
            if hasattr(entry, 'category'):  # If it's an AutorunEntry object
                category = entry.category
            else:  # If it's a dictionary
                category = entry.get('category', '')
            
            if category:  # Only add non-empty categories
                categories.add(category)
        
        categories = list(categories)
        categories.sort()  # Sort alphabetically
        
        # Block signals to prevent triggering filter during update
        self.cmb_category.blockSignals(True)
        
        # Clear and re-add items
        self.cmb_category.clear()
        self.cmb_category.addItem("全部类别")
        self.cmb_category.addItems(categories)
        
        # Unblock signals
        self.cmb_category.blockSignals(False)
    
    def cleanup(self):
        """清理资源"""
        self._icon_warmup_active = False
        for entry_id, worker in list(self._signature_workers_by_entry_id.items()):
            worker.quit()
            worker.wait(1000)
            self._cleanup_signature_worker(worker, entry_id)
        self._signature_workers_by_entry_id.clear()
        self.scan_controller.cleanup()
    
    def _is_suspicious(self, entry: dict) -> bool:
        """判断是否可疑"""
        # 未签名
        if entry.get('signer', '') and '(Verified)' not in entry.get('signer', ''):
            return True
        # 文件不存在
        if 'not found' in entry.get('image_path', '').lower():
            return True
        # 非微软签名的系统路径
        if 'windows' in entry.get('image_path', '').lower() and 'Microsoft' not in entry.get('signer', ''):
            return True
        return False
    

    
    def _on_category_filter_changed(self, text):
        """类别过滤变化时触发"""
        self._show_detail_placeholder()
        self._schedule_filter_table()
    
    def _on_filter_option_changed(self, state):
        """过滤选项变化时触发"""
        self._schedule_filter_table()

    def _schedule_filter_table(self):
        """搜索输入去抖，避免每次按键都触发过滤刷新"""
        self._filter_debounce_timer.start()
    
    def _filter_table(self):
        """过滤表格内容 - 现在使用代理模型"""
        timer = QElapsedTimer()
        timer.start()
        search_text = self.search_box.text()
        selected_category = self.cmb_category.currentText()
        show_suspicious_only = self.chk_suspicious.isChecked()

        if hasattr(self.proxy_model, 'apply_filters'):
            normalized_search = (search_text or "").lower()
            normalized_category = selected_category or "全部类别"
            normalized_suspicious_only = bool(show_suspicious_only)
            if (
                self.proxy_model.search_text == normalized_search
                and self.proxy_model.selected_category == normalized_category
                and self.proxy_model.show_suspicious_only == normalized_suspicious_only
            ):
                self._log_perf_if_slow(
                    "filter_skip",
                    timer,
                    self._perf_threshold_filter_ms,
                    extra=f"search_len={len(search_text)}",
                )
                return

        self.tree_view.setUpdatesEnabled(False)
        try:
            if hasattr(self.proxy_model, 'apply_filters'):
                self.proxy_model.apply_filters(
                    search_text=search_text,
                    selected_category=selected_category,
                    show_suspicious_only=show_suspicious_only,
                )
            else:
                self.proxy_model.set_search_text(search_text)
                self.proxy_model.set_selected_category(selected_category)
                self.proxy_model.set_show_suspicious_only(show_suspicious_only)
        finally:
            self.tree_view.setUpdatesEnabled(True)
            visible_rows = self.proxy_model.rowCount()
            total_rows = self.model.rowCount()
            self._log_perf_if_slow(
                "filter_table",
                timer,
                self._perf_threshold_filter_ms,
                extra=(
                    f"search_len={len(search_text)} "
                    f"category={selected_category} suspicious={int(show_suspicious_only)} "
                    f"visible={visible_rows}/{total_rows}"
                ),
            )

    def _on_model_reset(self):
        """模型重置后调整列宽（按分析优先级）"""
        # Category：固定宽度
        self.tree_view.setColumnWidth(0, AUTORUNS_CATEGORY_WIDTH)

        if not self._column_widths_initialized:
            # 首轮扫描完成后做一次性列宽采样，后续避免重复重计算
            self.tree_view.resizeColumnToContents(1)
            if self.tree_view.columnWidth(1) > AUTORUNS_ENTRY_MAX_WIDTH:
                self.tree_view.setColumnWidth(1, AUTORUNS_ENTRY_MAX_WIDTH)

            self.tree_view.resizeColumnToContents(2)
            if self.tree_view.columnWidth(2) > AUTORUNS_DESC_MAX_WIDTH:
                self.tree_view.setColumnWidth(2, AUTORUNS_DESC_MAX_WIDTH)

            self.tree_view.resizeColumnToContents(3)
            if self.tree_view.columnWidth(3) > AUTORUNS_PUBLISHER_MAX_WIDTH:
                self.tree_view.setColumnWidth(3, AUTORUNS_PUBLISHER_MAX_WIDTH)
            self._column_widths_initialized = True
        else:
            self.tree_view.setColumnWidth(1, AUTORUNS_ENTRY_MAX_WIDTH)
            self.tree_view.setColumnWidth(2, AUTORUNS_DESC_MAX_WIDTH)
            self.tree_view.setColumnWidth(3, AUTORUNS_PUBLISHER_MAX_WIDTH)
        
        # Image Path：使用剩余空间
        self.tree_view.header().setStretchLastSection(True)
    
    def _populate_tree(self, data):
        """填充树形视图"""
        timer = QElapsedTimer()
        timer.start()
        try:
            _debug_log(f"[AutorunsTab] _populate_tree 开始，data 长度: {len(data)}")
            self._show_detail_placeholder()
            
            _debug_log("[AutorunsTab] 清空模型")
            self.model.clear()
            
            _debug_log("[AutorunsTab] 添加条目到模型")
            self.model.add_entries(data)
            
            _debug_log("[AutorunsTab] _populate_tree 完成")
            self._log_perf_if_slow(
                "populate_tree",
                timer,
                self._perf_threshold_model_ms,
                extra=f"entries={len(data)}",
            )
        except Exception as e:
            import traceback
            _debug_log(f"[AutorunsTab] _populate_tree 错误: {e}")
            _debug_log(f"[AutorunsTab] 错误堆栈:\n{traceback.format_exc()}")
            self._log_perf_if_slow(
                "populate_tree_failed",
                timer,
                self._perf_threshold_model_ms,
                extra=f"entries={len(data)}",
            )
    
    def _on_context_menu(self, pos):
        """右键菜单"""
        from PyQt6.QtWidgets import QMenu
        
        # 获取点击位置的索引
        index = self.tree_view.indexAt(pos)
        if not index.isValid():
            return
        
        source_index = self.proxy_model.mapToSource(index)
        node = source_index.internalPointer()
        if not node:
            return
        
        # 获取节点数据
        data = node.data
        image_path = data.get('image_path', '')
        category = data.get('category', '')
        
        # 创建右键菜单
        menu = QMenu(self)
        
        # 主节点菜单
        # 计算 Hash
        action_hash = menu.addAction("计算 Hash")
        action_hash.triggered.connect(lambda: self._calculate_hash(data))
        
        # 重新验证签名
        action_verify = menu.addAction("重新验证签名")
        action_verify.triggered.connect(lambda: self._verify_signature(data))
        
        menu.addSeparator()
        
        # 删除条目
        action_delete = menu.addAction("删除条目")
        action_delete.triggered.connect(lambda: self._delete_entry(data))
        
        menu.addSeparator()
        
        # 复制文件并加密压缩
        if image_path and image_path.lower() != 'file not found':
            import os
            if os.path.exists(image_path):
                action_copy_encrypt = menu.addAction("复制文件并加密压缩")
                action_copy_encrypt.triggered.connect(lambda: self._copy_and_encrypt_file(data))
        
        menu.addSeparator()
        
        # 在资源管理器中打开
        if image_path and image_path.lower() != 'file not found':
            action_open = menu.addAction("在资源管理器中打开")
            action_open.triggered.connect(lambda: self._open_in_explorer(image_path))

        # 计划任务条目：快速打开任务计划程序，并复制任务名/路径
        is_scheduled_task = category == "Scheduled Tasks" or "Tasks" in str(data.get("location", ""))
        if is_scheduled_task:
            action_task_scheduler = menu.addAction("打开任务计划程序并复制任务标识")
            action_task_scheduler.triggered.connect(lambda: self._open_task_scheduler_for_entry(data))
        
        menu.addSeparator()
        
        # 在工作台中搜索
        action_hunt = menu.addAction("在工作台中搜索")
        action_hunt.triggered.connect(lambda: self._search_in_workspace(data))
        
        # 显示菜单
        menu.exec(self.tree_view.viewport().mapToGlobal(pos))
    
    def _show_detail_placeholder(self):
        self._detail_renderer.show_placeholder()

    def _schedule_detail_refresh(self, detail_data):
        self._pending_detail_data = detail_data
        if self._detail_refresh_scheduled:
            return
        self._detail_refresh_scheduled = True
        QTimer.singleShot(0, self._flush_detail_refresh)

    def _flush_detail_refresh(self):
        self._detail_refresh_scheduled = False
        detail_data = self._pending_detail_data
        self._pending_detail_data = None

        if not detail_data:
            if self._detail_renderer.current_entry_id is not None:
                self._show_detail_placeholder()
            return

        entry_id = detail_data.get('id')
        if entry_id and entry_id == self._detail_renderer.current_entry_id:
            return
        self._render_detail(detail_data)

    def _on_selection_changed(self, selected, deselected):
        """选中变化时触发（合并高频事件）"""
        if not selected.indexes():
            self._schedule_detail_refresh(None)
            return

        index = selected.indexes()[0]
        if not index.isValid():
            self._schedule_detail_refresh(None)
            return

        source_index = self.proxy_model.mapToSource(index)
        node = source_index.internalPointer()
        self._schedule_detail_refresh(node.data if node else None)

    def _render_detail(self, data):
        """渲染 Detail Pane（双栏 + 底部全宽排版）"""
        timer = QElapsedTimer()
        timer.start()
        self._detail_renderer.render_detail(data, self.format_file_size)
        entry_id = self._detail_renderer.current_entry_id
        self._log_perf_if_slow(
            "render_detail",
            timer,
            self._perf_threshold_detail_ms,
            extra=f"entry_id={entry_id}",
        )
    
    def _clear_detail_layout(self):
        """清空 Detail 布局"""
        self._detail_renderer.clear()
    
    def _on_entry_updated(self, entry_id):
        """Entry 更新时的回调"""
        if self._detail_renderer.current_entry_id == entry_id:
            node = self.model.get_node_by_id(entry_id)
            if node:
                self._render_detail(node.data)
    
    def _calculate_hash(self, data):
        """计算 Hash"""
        image_path = data.get('image_path', '')
        if not image_path or image_path.lower() == 'file not found':
            QMessageBox.warning(self, "警告", "无法计算哈希：文件路径无效")
            return
        
        try:
            hash_result = self.parser.calculate_file_hash(image_path)
            md5 = hash_result.get('md5', '')
            sha256 = hash_result.get('sha256', '')
            
            message = f"文件: {image_path}\n\n"
            if md5 and md5 != 'N/A':
                message += f"MD5: {md5}\n"
            if sha256 and sha256 != 'N/A':
                message += f"SHA256: {sha256}\n"
            
            QMessageBox.information(self, "Hash 计算结果", message)
            
            # 写回 entry 数据
            entry_id = data.get('id')
            if entry_id:
                node = self.model.get_node_by_id(entry_id)
                if node:
                    node.data['sha256'] = sha256
                    node.data['md5'] = md5
                    # 更新 detail_data
                    if 'detail_data' in node.data:
                        node.data['detail_data']['hash'] = sha256
                    # 刷新缓存并更新 UI
                    self.model.refresh_node(node)
                    self.model.emit_node_changed(node)
                    # 发出 entry_updated 信号，触发 Detail Pane 同步刷新
                    self.model.entry_updated.emit(entry_id)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算 Hash 失败: {str(e)}")
    
    def _update_signature_state(self, entry_id: str, signer_status: str, signature_detail: str, publisher: str = ""):
        """更新签名状态并同步刷新模型缓存"""
        if not entry_id:
            return None
        node = self.model.get_node_by_id(entry_id)
        if not node:
            return None
        node.data['signer_status'] = signer_status
        node.data['signature_detail'] = signature_detail
        detail = node.data.get('detail_data')
        if isinstance(detail, dict):
            if '(Verified)' in signer_status:
                detail['signature'] = 'Verified'
            elif '(Error)' in signer_status:
                detail['signature'] = 'Error'
            else:
                detail['signature'] = 'Unsigned'
            if publisher:
                detail['publisher'] = publisher
        self.model.refresh_node(node)
        self.model.emit_node_changed(node)
        return node

    def _refresh_detail_if_selected(self, entry_id: str, node):
        if not entry_id or node is None:
            return
        current_selection = self.tree_view.selectionModel().selectedIndexes()
        if not current_selection:
            return
        selected_index = self.proxy_model.mapToSource(current_selection[0])
        selected_node = selected_index.internalPointer()
        if selected_node and selected_node.data.get('id') == entry_id:
            self._render_detail(node.data)

    def _verify_signature(self, data):
        """重新验证签名"""
        image_path = data.get('image_path', '')
        if not image_path or image_path.lower() == 'file not found':
            QMessageBox.warning(self, "警告", "无法验证签名：文件路径无效")
            return

        entry_id = data.get('id')
        if not entry_id:
            QMessageBox.warning(self, "警告", "无法验证签名：条目ID缺失")
            return

        base_dir = os.path.dirname(os.path.dirname(__file__))
        sigcheck_path = os.path.join(base_dir, "tools", "sigcheck64.exe")
        if not os.path.exists(sigcheck_path):
            QMessageBox.warning(self, "警告", f"sigcheck64.exe 不存在: {sigcheck_path}")
            return

        running_worker = self._signature_workers_by_entry_id.get(entry_id)
        if running_worker and running_worker.isRunning():
            QMessageBox.information(self, "提示", "该条目正在进行签名验证，请稍候。")
            return

        # 使用 Windows 本地编码解码输出
        encoding = locale.getpreferredencoding(False)
        worker = SignatureVerifyWorker(entry_id, image_path, sigcheck_path, encoding)
        worker.succeeded.connect(self._on_verify_signature_succeeded)
        worker.failed.connect(self._on_verify_signature_failed)
        worker.finished.connect(lambda: self._cleanup_signature_worker(worker, entry_id))
        self._signature_workers.add(worker)
        self._signature_workers_by_entry_id[entry_id] = worker
        worker.start()

    def _cleanup_signature_worker(self, worker, entry_id: str = ""):
        try:
            self._signature_workers.discard(worker)
            if entry_id and self._signature_workers_by_entry_id.get(entry_id) is worker:
                self._signature_workers_by_entry_id.pop(entry_id, None)
            worker.deleteLater()
        except Exception:
            pass

    def _on_verify_signature_succeeded(self, payload):
        entry_id = payload.get("entry_id")
        image_path = payload.get("image_path", "")
        output = payload.get("output", "")

        QMessageBox.information(self, "签名验证结果", f"文件: {image_path}\n\n{output}")
        parsed = parse_sigcheck_output(output)
        node = self._update_signature_state(
            entry_id=entry_id,
            signer_status=parsed.signer_status,
            signature_detail=parsed.signature_detail,
            publisher=parsed.publisher,
        )
        self._refresh_detail_if_selected(entry_id, node)

    def _on_verify_signature_failed(self, payload):
        entry_id = payload.get("entry_id")
        error_msg = payload.get("error_msg", "Unknown error")
        severity = payload.get("severity", "warning")

        if severity == "critical":
            QMessageBox.critical(self, "错误", f"签名验证失败: {error_msg}")
        else:
            QMessageBox.warning(self, "警告", f"签名验证失败: {error_msg}")

        self._update_signature_state(entry_id, "(Error)", error_msg)
    
    def _open_in_explorer(self, path):
        """在资源管理器中打开文件（安全方式：打开目录并选中文件）"""
        try:
            import os
            if os.path.exists(path):
                if os.path.isdir(path):
                    subprocess.run(['explorer', path], check=False)
                else:
                    subprocess.run(['explorer', '/select,', path], check=False)
            else:
                QMessageBox.warning(self, "警告", f"文件不存在: {path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件: {str(e)}")
    
    def _search_in_workspace(self, data):
        """在工作台中搜索"""
        try:
            image_path = data.get('image_path', '')
            if image_path:
                self.search_in_workspace.emit(image_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"搜索失败: {str(e)}")

    def jump_to_entry(self, entry: dict):
        """跳转到指定的 Autoruns 条目"""
        try:
            if not entry:
                return
            target_entry = entry.get('entry', '')
            target_location = entry.get('location', '')
            if not target_entry:
                return

            source_model = self.model
            proxy_model = self.proxy_model
            view = self.tree_view

            node = source_model.get_node_by_entry_location(target_entry, target_location)
            if not node:
                return

            source_index = source_model.get_source_index_for_node(node)
            if not source_index.isValid():
                return
            proxy_index = proxy_model.mapFromSource(source_index)
            if proxy_index.isValid():
                view.setCurrentIndex(proxy_index)
                view.scrollTo(proxy_index)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"跳转失败: {str(e)}")


    def _on_scan_error(self, error_msg, elapsed):
        """扫描错误处理"""
        self._icon_warmup_active = False
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)
        self.lbl_scan_status.setText(f"错误: {error_msg}")
        self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
        self._show_detail_placeholder()
        QMessageBox.critical(self, "扫描错误", error_msg)
    
    def _delete_selected(self):
        """删除选中项"""
        # 获取 QTreeView 中的选中索引
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "警告", "请选择要删除的项目")
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除选中的 {len(selected_indexes)} 个项目吗？\n\n这是危险操作，请谨慎！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            for index in selected_indexes:
                # 将代理模型的索引转换为源模型的索引
                source_index = self.proxy_model.mapToSource(index)
                node = source_index.internalPointer()
                entry_data = node.data if node and isinstance(node.data, dict) else None
                if not entry_data:
                    continue

                from core.autoruns_parser import AutorunEntry

                entry = AutorunEntry(
                    location=entry_data.get('location', ''),
                    entry=entry_data.get('entry', ''),
                    enabled=entry_data.get('enabled', ''),
                    category=entry_data.get('category', ''),
                    description=entry_data.get('description', ''),
                    publisher=entry_data.get('publisher', ''),
                    company=entry_data.get('company', ''),
                    image_path=entry_data.get('image_path', ''),
                    launch_string=entry_data.get('launch_string', ''),
                    timestamp=entry_data.get('timestamp', ''),
                    signer=entry_data.get('signer', ''),
                    signer_status=entry_data.get('signer_status', ''),
                    signature_detail=entry_data.get('signature_detail', ''),
                    file_size=entry_data.get('file_size', ''),
                    file_version=entry_data.get('file_version', ''),
                    service_name=entry_data.get('service_name', ''),
                )

                success, message = self.parser.delete_entry(entry)
                if not success:
                    QMessageBox.warning(self, "删除失败", f"删除 {entry.entry} 失败: {message}")
                else:
                    QMessageBox.information(self, "删除成功", f"{message}")
        
            # 重新扫描以查看更改
            self._start_scan()
            
        except Exception as e:
            QMessageBox.critical(self, "删除错误", f"删除过程中发生错误: {str(e)}")
    

    



    def _delete_entry(self, data):
        """删除持久化条目"""
        _debug_log("[DeleteEntry] 开始删除条目")
        
        entry_name = data.get('entry', '')
        category = data.get('category', '')
        launch_string = data.get('launch_string', '')
        image_path = data.get('image_path', '')
        service_name = data.get('service_name', '')
        
        _debug_log("[DeleteEntry] 条目信息:")
        _debug_log(f"  - entry_name: {entry_name}")
        _debug_log(f"  - category: {category}")
        _debug_log(f"  - launch_string: {launch_string}")
        _debug_log(f"  - image_path: {image_path}")
        _debug_log(f"  - service_name: {service_name}")
        
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除条目 '{entry_name}' 吗？\n\n"
            f"类型: {category}\n"
            f"路径: {image_path}\n\n"
            f"这是危险操作，请谨慎！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            _debug_log("[DeleteEntry] 用户取消删除")
            return
        
        try:
            _debug_log("[DeleteEntry] 创建 AutorunEntry 对象")
            # 创建 AutorunEntry 对象
            from core.autoruns_parser import AutorunEntry
            entry = AutorunEntry(
                location=data.get('location', ''),
                entry=entry_name,
                enabled=data.get('enabled', ''),
                category=category,
                description=data.get('description', ''),
                publisher=data.get('publisher', ''),
                company=data.get('company', ''),
                image_path=image_path,
                launch_string=launch_string,
                timestamp=data.get('timestamp', ''),
                signer=data.get('signer', ''),
                signer_status=data.get('signer_status', ''),
                signature_detail=data.get('signature_detail', ''),
                file_size=data.get('file_size', ''),
                file_version=data.get('file_version', ''),
                service_name=service_name
            )
            
            _debug_log("[DeleteEntry] AutorunEntry 对象创建完成")
            _debug_log("[DeleteEntry] 调用 parser.delete_entry")
            
            # 根据类型删除
            success, message = self.parser.delete_entry(entry)
            
            _debug_log(f"[DeleteEntry] 删除结果: success={success}, message={message}")
            
            if success:
                QMessageBox.information(self, "删除成功", message)
                
                _debug_log("[DeleteEntry] 从模型中移除条目")
                # 从模型中移除该条目
                entry_id = data.get('id')
                removed = self.model.remove_node_by_id(entry_id) if entry_id else False
                if removed:
                    _debug_log("[DeleteEntry] 条目已从模型中移除")
                
                _debug_log("[DeleteEntry] 清空 Detail Pane")
                # 清空 Detail Pane
                self._show_detail_placeholder()
            else:
                _debug_log("[DeleteEntry] 删除失败")
                QMessageBox.warning(self, "删除失败", f"删除失败: {message}")
                
        except Exception as e:
            import traceback
            _debug_log(f"[DeleteEntry] 删除过程中发生错误: {e}")
            _debug_log(f"[DeleteEntry] 错误堆栈:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "删除错误", f"删除过程中发生错误: {str(e)}")
    
    def _copy_and_encrypt_file(self, data):
        """复制文件并加密压缩
        
        DEPRECATED: 此方法已废弃，请使用工作台的加密压缩功能
        工作台支持统一路径选择（self / directory / parent）和命令预览
        """
        import os
        
        image_path = data.get('image_path', '')
        entry_name = data.get('entry', '')

        # 校验文件是否存在
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self, "警告", "文件不存在，无法复制")
            return

        try:
            import pyzipper

            # 获取 SHA256 前三位
            sha256 = data.get('sha256', '')
            sha256_prefix = sha256[:3] if sha256 else '000'
            
            # 压缩包命名规则：<entry_name>_<sha256前三位>.zip
            safe_entry_name = self._sanitize_windows_filename(entry_name) or "sample"
            zip_filename = f"{safe_entry_name}_{sha256_prefix}.zip"
            
            # 默认密码为 1
            password = "1"
            
            # 询问保存位置
            from PyQt6.QtWidgets import QFileDialog
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存加密压缩文件",
                zip_filename,
                "ZIP 文件 (*.zip)"
            )
            
            if not save_path:
                return
            
            # 创建加密的 ZIP 文件
            with pyzipper.AESZipFile(save_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zipf:
                zipf.setpassword(password.encode('utf-8'))
                
                # 添加文件到 ZIP
                filename = os.path.basename(image_path)
                zipf.write(image_path, filename)
            
            QMessageBox.information(
                self,
                "压缩成功",
                f"文件已加密压缩并保存到：\n{save_path}\n\n密码: {password}"
            )
            
        except ImportError:
            QMessageBox.critical(
                self,
                "错误",
                "pyzipper 未安装或未打包，无法执行 AES 加密压缩。\n\n"
                "建议在工作台使用统一压缩功能，或在构建时确保包含 pyzipper。"
            )
        except PermissionError:
            QMessageBox.critical(self, "错误", "权限不足，无法访问文件")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"压缩过程中发生错误: {str(e)}")

    @staticmethod
    def _sanitize_windows_filename(name: str) -> str:
        text = str(name or "").strip()
        if not text:
            return ""
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            text = text.replace(ch, "_")
        text = text.rstrip(". ").strip()
        return text[:120]
    
    def _export_csv(self):
        """导出CSV"""
        if not self.model.root_nodes:
            QMessageBox.warning(self, "提示", "当前没有可导出的数据")
            return

        default_name = f"autoruns_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            default_name,
            "CSV 文件 (*.csv)",
        )
        if not save_path:
            return

        fieldnames = [
            "category",
            "entry",
            "description",
            "publisher",
            "image_path",
            "location",
            "enabled",
            "signer_status",
            "signature_detail",
            "timestamp",
            "command_line",
            "launch_string",
            "sha256",
            "file_size",
            "file_version",
            "service_name",
        ]

        try:
            with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for node in self.model.root_nodes:
                    if not node or not isinstance(node.data, dict):
                        continue
                    writer.writerow(node.data)
            QMessageBox.information(self, "导出成功", f"CSV 已导出到:\n{save_path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"导出 CSV 失败: {exc}")

    def _show_risk_help(self):
        """显示风险等级说明对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("风险等级说明")
        dialog.setMinimumSize(450, 350)

        layout = QVBoxLayout(dialog)

        # 标题
        title_label = QLabel("<h3>条目风险等级判定标准</h3>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # 内容区域
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setStyleSheet(AUTORUNS_RISK_HELP_TEXT_STYLESHEET)

        help_content = """
<p><b>🟢 明显可信 (SAFE)</b></p>
<ul>
<li>Microsoft 或其他可信发布者签名</li>
<li>位于系统目录 (System32 / Program Files)</li>
<li>签名验证通过</li>
</ul>
<p style="color: #2e7d32;">UI 表现：默认颜色，无特殊标记</p>

<p><b>🟡 可疑 (SUSPICIOUS)</b></p>
<ul>
<li>非系统目录下的可执行文件</li>
<li>发布者为空或未知</li>
<li>无有效数字签名</li>
</ul>
<p style="color: #b8860b;">UI 表现：Entry 列浅黄色强调，深金色字体，图标右下角黄色标记</p>

<p><b>🔴 高风险 (HIGH_RISK)</b></p>
<ul>
<li>文件不存在 (已被删除或移动)</li>
<li>无签名 + 位于用户可写目录 (AppData / Temp / Downloads 等)</li>
<li>典型的恶意软件驻留路径</li>
</ul>
<p style="color: #8b0000;">UI 表现：Entry 列浅红色强调，深红色字体，图标右下角红色标记</p>

<p><b>💡 提示</b></p>
<ul>
<li>风险等级仅作为辅助分析参考，不是最终判定</li>
<li>建议结合签名验证、文件哈希、命令行参数综合判断</li>
<li>对于高风险条目，建议优先检查</li>
</ul>
"""
        content_text.setHtml(help_content)
        layout.addWidget(content_text)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def _open_task_scheduler_for_entry(self, data):
        """打开任务计划程序，并复制任务标识到剪贴板，便于人工快速定位。"""
        identifier, candidates = self._build_task_identifier(data)
        try:
            from PyQt6.QtGui import QGuiApplication

            subprocess.run(["taskschd.msc"], check=False)
            if identifier:
                QGuiApplication.clipboard().setText(identifier)
                candidate_text = "\n".join(f"- {item}" for item in candidates[:5])
                QMessageBox.information(
                    self,
                    "提示",
                    "已打开任务计划程序。\n\n"
                    f"已复制优先标识到剪贴板:\n{identifier}\n\n"
                    "可用于定位的候选标识:\n"
                    f"{candidate_text}",
                )
            else:
                QMessageBox.information(self, "提示", "已打开任务计划程序。")
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"打开任务计划程序失败: {exc}")

    def _build_task_identifier(self, data):
        """构建计划任务定位标识，返回 (primary, candidates)。"""
        task_entry = (data.get("entry", "") or "").strip()
        task_location = (data.get("location", "") or "").strip()
        task_command = (data.get("launch_string", "") or "").strip()

        candidates = []

        parsed_from_command = self._extract_task_name_from_command(task_command)
        if parsed_from_command:
            candidates.append(parsed_from_command)

        # 常见 entry 为任务名，优先级高于 location。
        if task_entry:
            candidates.append(task_entry)
        if task_location:
            candidates.append(task_location)
        if task_command:
            candidates.append(task_command)

        dedup = []
        seen = set()
        for item in candidates:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)

        primary = dedup[0] if dedup else ""
        return primary, dedup

    @staticmethod
    def _extract_task_name_from_command(command: str) -> str:
        """从 schtasks 命令行中提取 /tn 任务名。"""
        text = (command or "").strip()
        if not text:
            return ""
        lower = text.lower()
        pos = lower.find("/tn")
        if pos < 0:
            return ""

        rest = text[pos + 3 :].strip()
        if not rest:
            return ""

        if rest.startswith('"'):
            end_quote = rest.find('"', 1)
            if end_quote > 1:
                return rest[1:end_quote].strip()
            return rest.strip('"').strip()

        token = rest.split()[0] if rest.split() else ""
        return token.strip()
