# ui/autoruns_tab.py
import subprocess
import sys
import time
import uuid
import locale
from dataclasses import dataclass, asdict
from typing import List, Optional
import hashlib
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QAbstractItemView,
    QCheckBox, QComboBox, QLineEdit, QPushButton, QMessageBox,
    QLabel, QFrame, QSplitter, QTextEdit, QGridLayout, QScrollArea,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, QThread, pyqtSignal, QSortFilterProxyModel, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from core.autoruns_parser import AutorunsParser
from core.icon_provider import get_icon, IconProvider
from core.risk_hint import get_risk_evaluator, RiskLevel, get_risk_color, get_risk_foreground_color
from ui.ui_style import apply_flat_style




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
        self._icon_provider = IconProvider()
        self._risk_evaluator = get_risk_evaluator()
        self._risk_cache = {}  # 缓存风险评估结果

    def _compose_publisher_display(self, entry_data: dict) -> str:
        publisher = entry_data.get('publisher', '')
        signer_status = entry_data.get('signer_status', '')
        if '(Verified)' in signer_status:
            return f"(Verified) {publisher}"
        if '(Error)' in signer_status:
            error_reason = entry_data.get('signature_detail', 'Unknown error')
            return f"(Error) {error_reason}"
        return "(Unsigned)"

    def _refresh_entry_cache(self, entry_data: dict, invalidate_risk: bool = True):
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

        if invalidate_risk:
            entry_id = entry_data.get('id')
            if entry_id:
                self._risk_cache.pop(entry_id, None)

    def refresh_node(self, node):
        """节点数据更新后刷新缓存"""
        if not node or not isinstance(node.data, dict):
            return
        self._refresh_entry_cache(node.data, invalidate_risk=True)

    def emit_node_changed(self, node):
        """统一发出节点刷新信号"""
        if not node:
            return
        try:
            row = self.root_nodes.index(node)
        except ValueError:
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
        elif role == Qt.ItemDataRole.DecorationRole:
            # 图标显示：只在 Entry 列（第1列）显示
            if index.column() == 1:
                image_path = node.data.get('image_path', '')
                risk_level = self._get_cached_risk_level(node)
                return self._icon_provider.get_icon_with_overlay(image_path, risk_level)
        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._get_row_foreground_color(node, index.column())
        elif role == Qt.ItemDataRole.BackgroundRole:
            return self._get_row_background_color(node)
        elif role == Qt.ItemDataRole.UserRole:
            return node.data

        return None

    def _get_cached_risk_level(self, node) -> int:
        """获取缓存的风险等级"""
        entry_id = node.data.get('id', '')
        if not entry_id:
            # 无 ID 时实时计算
            risk_hint = self._risk_evaluator.evaluate(node.data)
            return risk_hint.level

        if entry_id not in self._risk_cache:
            risk_hint = self._risk_evaluator.evaluate(node.data)
            self._risk_cache[entry_id] = risk_hint.level

        return self._risk_cache[entry_id]
    
    def _get_row_foreground_color(self, node, column):
        """根据条目状态返回前景颜色（字体颜色）- 使用风险评估"""
        # 只对 Entry 列（第 1 列）应用颜色
        if column != 1:
            return None

        risk_level = self._get_cached_risk_level(node)

        # 根据风险等级返回颜色
        if risk_level == RiskLevel.HIGH_RISK:
            return QColor(139, 0, 0)  # 深红色
        elif risk_level == RiskLevel.SUSPICIOUS:
            return QColor(184, 134, 11)  # 深金色

        return None

    def _get_row_background_color(self, node):
        """根据条目状态返回背景颜色 - 使用风险评估"""
        risk_level = self._get_cached_risk_level(node)

        # 根据风险等级返回背景色
        if risk_level == RiskLevel.HIGH_RISK:
            return QColor(255, 228, 225)  # 浅红色（MistyRose）
        elif risk_level == RiskLevel.SUSPICIOUS:
            return QColor(255, 248, 220)  # 浅黄色（Cornsilk）

        return None

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
        
        try:
            print(f"[Model] 开始添加 {len(entries)} 个条目")
            
            # 为大量数据批量插入做准备
            self.beginResetModel()
            
            # 清空现有数据
            self.root_nodes.clear()
            self._risk_cache.clear()
            
            # 批量添加数据
            for i, entry in enumerate(entries):
                try:
                    # 处理 AutorunEntry 对象或字典
                    if hasattr(entry, 'entry'):  # 如果是 AutorunEntry 对象
                        entry_val = getattr(entry, 'entry', '')
                        description = getattr(entry, 'description', '')
                        publisher = getattr(entry, 'publisher', '')
                        company = getattr(entry, 'company', '')
                        image_path = getattr(entry, 'image_path', '')
                        timestamp = getattr(entry, 'timestamp', '')
                        category = getattr(entry, 'category', '')
                        location = getattr(entry, 'location', '')
                        enabled = getattr(entry, 'enabled', '')
                        signer_status = getattr(entry, 'signer_status', '')
                        launch_string = getattr(entry, 'launch_string', '')
                        command_line = getattr(entry, 'command_line', '') or launch_string
                        signature_detail = getattr(entry, 'signature_detail', '')
                        sha256 = getattr(entry, 'sha256', '')
                        file_size = getattr(entry, 'file_size', '')
                        file_version = getattr(entry, 'file_version', '')
                        service_name = getattr(entry, 'service_name', '')
                        file_exists = getattr(entry, 'file_exists', True)
                        
                        # 使用 get_detail_data() 方法获取结构化 detail 数据
                        if hasattr(entry, 'get_detail_data'):
                            detail_data = entry.get_detail_data()
                            # 统一编码处理
                            if 'publisher' in detail_data and detail_data['publisher']:
                                try:
                                    detail_data['publisher'] = detail_data['publisher'].encode('utf-8', errors='replace').decode('utf-8')
                                except Exception:
                                    pass
                            if 'company' in detail_data and detail_data['company']:
                                try:
                                    detail_data['company'] = detail_data['company'].encode('utf-8', errors='replace').decode('utf-8')
                                except Exception:
                                    pass
                        else:
                            # 统一编码处理
                            if publisher:
                                try:
                                    publisher = publisher.encode('utf-8', errors='replace').decode('utf-8')
                                except Exception:
                                    pass
                            if company:
                                try:
                                    company = company.encode('utf-8', errors='replace').decode('utf-8')
                                except Exception:
                                    pass
                            
                            detail_data = {
                                "image_path": image_path,
                                "command_line": command_line,
                                "category": category,
                                "timestamp": timestamp,
                                "signature": "Unsigned",
                                "publisher": publisher,
                                "company": company,
                                "size": file_size,
                                "version": file_version,
                                "hash": sha256
                            }
                    else:  # 如果是字典
                        entry_val = entry.get('entry', '')
                        description = entry.get('description', '')
                        publisher = entry.get('publisher', '')
                        company = entry.get('company', '')
                        image_path = entry.get('image_path', '')
                        timestamp = entry.get('timestamp', '')
                        category = entry.get('category', '')
                        location = entry.get('location', '')
                        enabled = entry.get('enabled', '')
                        signer_status = entry.get('signer_status', '')
                        launch_string = entry.get('launch_string', '')
                        command_line = entry.get('command_line', '') or launch_string
                        signature_detail = entry.get('signature_detail', '')
                        sha256 = entry.get('sha256', '')
                        file_size = entry.get('file_size', '')
                        file_version = entry.get('file_version', '')
                        service_name = entry.get('service_name', '')
                        file_exists = entry.get('file_exists', True)
                        
                        detail_data = {
                            "image_path": image_path,
                            "command_line": command_line,
                            "category": category,
                            "timestamp": timestamp,
                            "signature": "Unsigned",
                            "publisher": publisher,
                            "company": company,
                            "size": file_size,
                            "version": file_version,
                            "hash": sha256
                        }
                    
                    # 创建主节点
                    main_data = {
                        'id': str(uuid.uuid4()),
                        'entry': entry_val,
                        'description': description,
                        'publisher': publisher,
                        'company': company,
                        'image_path': image_path,
                        'timestamp': timestamp,
                        'category': category,
                        'location': location,
                        'enabled': enabled,
                        'signer_status': signer_status,
                        'launch_string': launch_string,
                        'command_line': command_line,
                        'signature_detail': signature_detail,
                        'sha256': sha256,
                        'file_size': file_size,
                        'file_version': file_version,
                        'service_name': service_name,
                        'file_exists': file_exists,
                        'detail_data': detail_data
                    }
                    self._refresh_entry_cache(main_data, invalidate_risk=False)
                    
                    main_node = TreeNode(main_data)
                    self.root_nodes.append(main_node)
                except Exception as e:
                    import traceback
                    print(f"[Model] 处理第 {i} 个条目时出错: {e}")
                    print(f"[Model] 错误堆栈:\n{traceback.format_exc()}")
                    continue
            
            # 结束重置
            self.endResetModel()
            print(f"[Model] 添加条目完成，共 {len(self.root_nodes)} 个条目")
            
        except Exception as e:
            import traceback
            print(f"[Model] 添加条目时发生严重错误: {e}")
            print(f"[Model] 错误堆栈:\n{traceback.format_exc()}")
            # 确保调用 endResetModel
            try:
                self.endResetModel()
            except:
                pass
    
    def clear(self):
        """清空模型"""
        if self.root_nodes:
            self.beginRemoveRows(QModelIndex(), 0, len(self.root_nodes) - 1)
            self.root_nodes.clear()
            self.endRemoveRows()
        # 清除风险缓存
        self._risk_cache.clear()


class AutorunsFilterProxyModel(QSortFilterProxyModel):
    """自定义过滤代理模型，确保Level-1行不参与过滤"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.selected_category = "全部类别"
        self.show_suspicious_only = False
    
    def set_search_text(self, text):
        """设置搜索文本"""
        self.search_text = text.lower()
        self.invalidateFilter()
    
    def set_selected_category(self, category):
        """设置选中的类别"""
        self.selected_category = category
        self.invalidateFilter()
    
    def set_show_suspicious_only(self, show_only):
        """设置是否仅显示可疑项"""
        self.show_suspicious_only = show_only
        self.invalidateFilter()
    
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

class AutorunsScanWorker(QThread):
    """扫描工作线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, parser, include_hash, verify_sig, category_filter):
        super().__init__()
        self.parser = parser
        self.include_hash = include_hash
        self.verify_sig = verify_sig
        self.category_filter = category_filter
        self._is_cancelled = False
    
    def cancel(self):
        """取消扫描"""
        self._is_cancelled = True
    
    def run(self):
        try:
            print(f"[ScanThread] 开始扫描，include_hash={self.include_hash}, verify_sig={self.verify_sig}")
            self.progress.emit("正在扫描自启动项...")
            entries = self.parser.scan(
                include_hash=self.include_hash,
                verify_signature=self.verify_sig,
                category_filter=self.category_filter
            )
            print(f"[ScanThread] 扫描完成，共 {len(entries)} 个条目")
            
            # Check if cancelled before emitting finished signal
            if not self._is_cancelled:
                print(f"[ScanThread] 转换为字典格式")
                entries_dict = [e.to_dict() for e in entries]
                print(f"[ScanThread] 发送 finished 信号")
                self.finished.emit(entries_dict)
            else:
                print(f"[ScanThread] 扫描已取消")
            
        except Exception as e:
            import traceback
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"[ScanThread] 扫描错误: {error_msg}")
            print(f"[ScanThread] 错误堆栈:\n{error_trace}")
            if not self._is_cancelled:
                self.error.emit(error_msg)

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
        self.current_worker = None  # 当前正在运行的工作线程
        self._is_scanning = False  # 扫描状态标志
        self._scan_start_time = None  # 扫描开始时间
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.btn_scan = QPushButton("开始扫描")
        self.btn_scan.clicked.connect(self._start_scan)
        
        self.btn_cancel = QPushButton("取消扫描")
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_cancel.setEnabled(False)  # 默认禁用，扫描时启用
        
        self.chk_hash = QCheckBox("计算Hash")
        self.chk_hash.setChecked(False)  # 默认不计算，加快速度

        
        self.chk_sig = QCheckBox("验证签名")
        self.chk_sig.setChecked(False)  # Default to disabled
        
        self.cmb_category = QComboBox()
        self.cmb_category.addItem("全部类别")
        self.cmb_category.currentTextChanged.connect(self._on_category_filter_changed)
        
        self.chk_suspicious = QCheckBox("仅显示可疑项")
        self.chk_suspicious.stateChanged.connect(self._on_filter_option_changed)
        
        # 添加搜索框
        search_label = QLabel("搜索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("类型/名称/描述/发布者/文件路径/启动命令")
        self.search_box.textChanged.connect(self._filter_table)
        
        self.btn_delete = QPushButton("删除选中项")
        self.btn_delete.clicked.connect(self._delete_selected)
        
        self.btn_export = QPushButton("导出CSV")
        self.btn_export.clicked.connect(self._export_csv)
        
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
        
        # 设置根节点不显示装饰箭头
        self.tree_view.setRootIsDecorated(False)

        # 性能优化：列表行高一致时可显著降低大数据滚动开销
        self.tree_view.setUniformRowHeights(True)
        
        # 设置交替行颜色
        self.tree_view.setAlternatingRowColors(True)
        
        # 设置样式：显示行分隔线（不覆盖 Model 的 BackgroundRole）
        self.tree_view.setStyleSheet("""
            QTreeView {
                border: 1px solid #d6dbe1;
                gridline-color: #e3e8ef;
                background-color: #ffffff;
                alternate-background-color: #f7f9fb;
            }
        """)
        
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
        detail_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        detail_layout.addWidget(detail_label)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #d6dbe1;
                background-color: #ffffff;
            }
        """)
        
        # Detail 内容容器
        self.detail_widget = QWidget()
        self.detail_layout = QGridLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(10, 10, 10, 10)
        self.detail_layout.setHorizontalSpacing(8)
        self.detail_layout.setVerticalSpacing(2)
        
        # 初始状态：显示提示文字
        self.detail_placeholder = QLabel("Select an entry to view details")
        self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
        self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
        
        # 存储当前显示的 entry_id
        self.current_entry_id = None
        
        # 存储字段标签
        self.detail_labels = {}
        
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
        # 设置样式确保正确显示
        self.btn_help.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 12px;
                text-align: center;
                padding: 0px;
                margin: 0px;
            }
        """)
        status_inner_layout.addWidget(self.btn_help)
        
        self.status_frame.setLayout(status_inner_layout)
        layout.addWidget(self.status_frame)
    
    def _start_scan(self):
        """开始扫描"""
        # 防止重复启动扫描
        if self._is_scanning:
            return
        
        # 检查是否选择了验证签名，如果是，则显示确认对话框
        if self.chk_sig.isChecked():
            reply = QMessageBox.question(
                self, "确认签名验证", 
                "验证签名功能需重新扫描，且扫描时间较长(18分钟左右)，是否继续？\n\n注意：此操作可能需要较长时间。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # 如果用户选择否，取消扫描
                return
        
        # 如果当前有正在运行的worker，则取消它
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        
        self._is_scanning = True
        self._scan_start_time = time.time()  # 记录开始时间
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("扫描中...")
        self.btn_cancel.setEnabled(True)  # 启用取消按钮
        
        # 更新状态栏
        self.lbl_scan_status.setText("扫描中...")
        self.lbl_scan_duration.setText("耗时: 0秒")
        self.lbl_total_items.setText("条目: 0")
        self.lbl_categories.setText("类别: 0")
        
        category_filter = None
        if self.cmb_category.currentIndex() > 0:
            category_filter = [self.cmb_category.currentText()]
        
        self.current_worker = AutorunsScanWorker(
            self.parser,
            include_hash=self.chk_hash.isChecked(),
            verify_sig=self.chk_sig.isChecked(),
            category_filter=category_filter
        )
        self.current_worker.finished.connect(self._on_scan_finished)
        self.current_worker.error.connect(self._on_scan_error)
        self.current_worker.progress.connect(self._on_scan_progress)
        self.current_worker.start()
    
    def _on_scan_progress(self, message):
         """扫描进度更新"""
         self.btn_scan.setText(message)
         # 更新状态栏中的扫描状态
         self.lbl_scan_status.setText(message)
         # 更新耗时
         if self._scan_start_time:
             elapsed = int(time.time() - self._scan_start_time)
             self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
    
    def _cancel_scan(self):
        """取消扫描"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()  # This will trigger cancellation
            self.current_worker.quit()
            self.current_worker.wait(5000)  # Wait up to 5 seconds
        
        # Reset UI state
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)  # Disable cancel button
        self._is_scanning = False
        
        # Update status bar
        self.lbl_scan_status.setText("已取消")
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
    
    def _on_scan_finished(self, data):
        """扫描完成处理"""
        print(f"[AutorunsTab] 扫描完成，收到 {len(data)} 个条目")
        
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)  # Disable cancel button
        self._is_scanning = False
        
        # Update status bar
        self.lbl_scan_status.setText("扫描完成")
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
        
        # Update stats
        self.current_data = data
        if self.data_store:
            self.data_store.set_autoruns_entries(self.current_data)
        self._update_stats()
        
        # Update category filter with unique categories from data
        self._update_category_filter(data)
        
        # 填充树形视图
        print(f"[AutorunsTab] 开始填充树形视图")
        self._populate_tree(data)
        print(f"[AutorunsTab] 树形视图填充完成")
        
        # Update status bar
        self.lbl_scan_status.setText("扫描完成")
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
        
        # Cleanup worker reference
        if self.current_worker:
            self.current_worker = None
    
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
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.current_worker.quit()
            self.current_worker.wait(5000)  # 等待最多5秒
    
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
        self._clear_detail_layout()
        self.detail_placeholder = QLabel("Select an entry to view details")
        self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
        self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
        self.current_entry_id = None
        self._filter_table()
    
    def _on_filter_option_changed(self, state):
        """过滤选项变化时触发"""
        self._filter_table()
    
    def _filter_table(self):
        """过滤表格内容 - 现在使用代理模型"""
        search_text = self.search_box.text()
        selected_category = self.cmb_category.currentText()
        show_suspicious_only = self.chk_suspicious.isChecked()
        
        # 禁用 UI 更新
        self.tree_view.setUpdatesEnabled(False)
        
        # 使用自定义代理模型的过滤方法
        if hasattr(self.proxy_model, 'set_search_text'):
            self.proxy_model.set_search_text(search_text)
            self.proxy_model.set_selected_category(selected_category)
            self.proxy_model.set_show_suspicious_only(show_suspicious_only)
        
        # 强制清理高度/布局缓存
        self.tree_view.collapseAll()
        self.tree_view.doItemsLayout()
        
        # 启用 UI 更新
        self.tree_view.setUpdatesEnabled(True)

    def _on_model_reset(self):
        """模型重置后调整列宽（按分析优先级）"""
        # Category：固定宽度
        self.tree_view.setColumnWidth(0, 100)
        
        # Entry：最大宽度 350
        self.tree_view.resizeColumnToContents(1)
        if self.tree_view.columnWidth(1) > 350:
            self.tree_view.setColumnWidth(1, 350)
        
        # Description：最大宽度 250
        self.tree_view.resizeColumnToContents(2)
        if self.tree_view.columnWidth(2) > 250:
            self.tree_view.setColumnWidth(2, 250)
        
        # Publisher：最大宽度 220
        self.tree_view.resizeColumnToContents(3)
        if self.tree_view.columnWidth(3) > 220:
            self.tree_view.setColumnWidth(3, 220)
        
        # Image Path：使用剩余空间
        self.tree_view.header().setStretchLastSection(True)
    
    def _populate_tree(self, data):
        """填充树形视图"""
        try:
            print(f"[AutorunsTab] _populate_tree 开始，data 长度: {len(data)}")
            
            self._clear_detail_layout()
            self.detail_placeholder = QLabel("Select an entry to view details")
            self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
            self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
            self.current_entry_id = None
            
            print(f"[AutorunsTab] 清空模型")
            self.model.clear()
            
            print(f"[AutorunsTab] 添加条目到模型")
            self.model.add_entries(data)
            
            print(f"[AutorunsTab] _populate_tree 完成")
        except Exception as e:
            import traceback
            print(f"[AutorunsTab] _populate_tree 错误: {e}")
            print(f"[AutorunsTab] 错误堆栈:\n{traceback.format_exc()}")
    
    def _on_context_menu(self, pos):
        """右键菜单"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QGuiApplication, QClipboard
        
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
        
        menu.addSeparator()
        
        # 在工作台中搜索
        action_hunt = menu.addAction("在工作台中搜索")
        action_hunt.triggered.connect(lambda: self._search_in_workspace(data))
        
        # 显示菜单
        menu.exec(self.tree_view.viewport().mapToGlobal(pos))
    
    def _on_selection_changed(self, selected, deselected):
        """选中变化时触发"""
        if not selected.indexes():
            # 选中为空，显示占位符
            self._clear_detail_layout()
            self.detail_placeholder = QLabel("Select an entry to view details")
            self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
            self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
            self.current_entry_id = None
            return
        
        # 获取第一个选中的索引
        index = selected.indexes()[0]
        if not index.isValid():
            return
        
        # 映射到源模型
        source_index = self.proxy_model.mapToSource(index)
        node = source_index.internalPointer()
        
        if not node:
            self._clear_detail_layout()
            self.detail_placeholder = QLabel("Select an entry to view details")
            self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
            self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
            self.current_entry_id = None
            return
        
        # 渲染 Detail
        self._render_detail(node.data)
    
    def _render_detail(self, data):
        """渲染 Detail Pane（双栏 + 底部全宽排版）"""
        detail_data = data.get('detail_data', {})
        entry_id = data.get('id')
        
        # 清空现有布局
        self._clear_detail_layout()
        
        # 展开 Detail Pane
        self.splitter.setSizes([700, 300])
        
        # 设置字体（字段名用正常大小，字段值用稍小字体）
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setFamily("Segoe UI, Arial, sans-serif")
        
        value_font = QFont()
        value_font.setPointSize(9)
        value_font.setFamily("Segoe UI, Arial, sans-serif")
        
        # 创建字段标签的辅助函数
        def create_field_label(key, value, is_selectable=True):
            label = QLabel(str(value) if value else "")
            label.setFont(value_font)
            label.setWordWrap(True)
            if is_selectable:
                label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return label
        
        def create_title_label(text):
            label = QLabel(text)
            label.setStyleSheet("font-weight: bold; color: #000;")
            label.setFont(title_font)
            return label
        
        # 获取签名状态
        signer_status = data.get('signer_status', '')
        signature_display = "Unsigned"
        signature_color = "#d32f2f"  # 红色
        
        if '(Verified)' in signer_status:
            signature_display = "Verified"
            signature_color = "#2e7d32"  # 绿色
        elif '(Error)' in signer_status:
            signature_display = f"Error: {data.get('signature_detail', 'Unknown error')}"
            signature_color = "#f57c00"  # 橙色
        
        # 检查文件是否存在
        import os
        image_path = detail_data.get('image_path', '')
        file_not_found = False
        if image_path and image_path.lower() != 'file not found':
            file_not_found = not os.path.exists(image_path)
        
        # 第一行：Entry | Size
        row = 0
        self.detail_layout.addWidget(create_title_label("Entry"), row, 0)
        self.detail_layout.addWidget(create_field_label('entry', data.get('entry', '')), row + 1, 0)
        self.detail_layout.addWidget(create_title_label("Size"), row, 1)
        size_display = self.format_file_size(detail_data.get('size', ''))
        self.detail_layout.addWidget(create_field_label('size', size_display), row + 1, 1)
        
        # 第二行：Description | Timestamp
        row += 2
        self.detail_layout.addWidget(create_title_label("Description"), row, 0)
        self.detail_layout.addWidget(create_field_label('description', data.get('description', '')), row + 1, 0)
        self.detail_layout.addWidget(create_title_label("Timestamp"), row, 1)
        self.detail_layout.addWidget(create_field_label('timestamp', detail_data.get('timestamp', '')), row + 1, 1)
        
        # 第三行：Publisher | Signature
        row += 2
        self.detail_layout.addWidget(create_title_label("Publisher"), row, 0)
        self.detail_layout.addWidget(create_field_label('publisher', detail_data.get('publisher', '')), row + 1, 0)
        self.detail_layout.addWidget(create_title_label("Signature"), row, 1)
        signature_label = create_field_label('signature', signature_display)
        signature_label.setStyleSheet(f"color: {signature_color}; font-weight: bold;")
        self.detail_layout.addWidget(signature_label, row + 1, 1)
        
        # 第四行：Version | Hash (SHA256)
        row += 2
        self.detail_layout.addWidget(create_title_label("Version"), row, 0)
        self.detail_layout.addWidget(create_field_label('version', detail_data.get('version', '')), row + 1, 0)
        self.detail_layout.addWidget(create_title_label("Hash (SHA256)"), row, 1)
        hash_value = detail_data.get('hash', '')
        hash_display = hash_value if hash_value else "Not calculated"
        self.detail_layout.addWidget(create_field_label('hash', hash_display), row + 1, 1)
        
        # 底部全宽字段：Image Path
        row += 2
        self.detail_layout.addWidget(create_title_label("Image Path"), row, 0, 1, 2)
        image_path_display = image_path
        if file_not_found:
            image_path_display = f"{image_path} (File not found)"
        image_label = create_field_label('image_path', image_path_display)
        bg_color = "#ffe0e0" if file_not_found else "#f0f0f0"
        image_label.setStyleSheet(f"background-color: {bg_color}; padding: 5px; border-radius: 3px;")
        self.detail_layout.addWidget(image_label, row + 1, 0, 1, 2)
        
        # 底部全宽字段：Command Line
        row += 2
        self.detail_layout.addWidget(create_title_label("Command Line"), row, 0, 1, 2)
        command_line = detail_data.get('command_line', '')
        cmd_label = create_field_label('command_line', command_line)
        cmd_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        self.detail_layout.addWidget(cmd_label, row + 1, 0, 1, 2)
        
        # 添加弹性空间
        self.detail_layout.setRowStretch(row + 2, 1)
        
        # 保存当前 entry_id
        self.current_entry_id = entry_id
    
    def _clear_detail_layout(self):
        """清空 Detail 布局"""
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.detail_labels.clear()
    
    def _on_entry_updated(self, entry_id):
        """Entry 更新时的回调"""
        if self.current_entry_id == entry_id:
            # 找到对应的节点并重新渲染
            for node in self.model.root_nodes:
                if node.data.get('id') == entry_id:
                    self._render_detail(node.data)
                    break
    
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
                for node in self.model.root_nodes:
                    if node.data.get('id') == entry_id:
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
                        break
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算 Hash 失败: {str(e)}")
    
    def _verify_signature(self, data):
        """重新验证签名"""
        image_path = data.get('image_path', '')
        if not image_path or image_path.lower() == 'file not found':
            QMessageBox.warning(self, "警告", "无法验证签名：文件路径无效")
            return
        
        # 使用 sigcheck64.exe 验证签名
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(__file__))
            sigcheck_path = os.path.join(base_dir, "tools", "sigcheck64.exe")
            
            if not os.path.exists(sigcheck_path):
                QMessageBox.warning(self, "警告", f"sigcheck64.exe 不存在: {sigcheck_path}")
                return
            
            # 使用 Windows 本地编码解码输出
            encoding = locale.getpreferredencoding(False)
            cmd = [sigcheck_path, '-accepteula', '-nobanner', image_path]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            # 使用本地编码解码输出
            stdout = result.stdout.decode(encoding, errors='replace')
            stderr = result.stderr.decode(encoding, errors='replace')
            
            if result.returncode == 0:
                output = stdout.strip()
                QMessageBox.information(self, "签名验证结果", f"文件: {image_path}\n\n{output}")
                
                # 解析签名状态
                signature_status = "(Unsigned)"
                signature_detail = ""
                parsed_publisher = ""
                parsed_company = ""
                
                if "verified" in output.lower():
                    signature_status = "(Verified)"
                    # 尝试提取签名者信息
                    lines = output.split('\n')
                    for line in lines:
                        if 'signer' in line.lower() or 'signed by' in line.lower():
                            signature_detail = line.strip()
                            # 尝试提取 publisher 和 company
                            if ':' in line:
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    parsed_publisher = parts[1].strip()
                                    # 编码处理
                                    try:
                                        parsed_publisher = parsed_publisher.encode(encoding, errors='replace').decode(encoding)
                                    except Exception:
                                        pass
                            break
                elif "error" in output.lower() or "failed" in output.lower():
                    signature_status = "(Error)"
                    signature_detail = output
                else:
                    signature_status = "(Unsigned)"
                    signature_detail = ""
                
                # 写回 entry 数据
                entry_id = data.get('id')
                if entry_id:
                    for node in self.model.root_nodes:
                        if node.data.get('id') == entry_id:
                            node.data['signer_status'] = signature_status
                            node.data['signature_detail'] = signature_detail
                            # 更新 detail_data
                            if 'detail_data' in node.data:
                                # 归一化签名状态
                                if '(Verified)' in signature_status:
                                    node.data['detail_data']['signature'] = 'Verified'
                                elif '(Error)' in signature_status:
                                    node.data['detail_data']['signature'] = 'Error'
                                else:
                                    node.data['detail_data']['signature'] = 'Unsigned'
                                # 更新 publisher
                                if parsed_publisher:
                                    node.data['detail_data']['publisher'] = parsed_publisher
                            # 刷新缓存并更新 UI
                            self.model.refresh_node(node)
                            self.model.emit_node_changed(node)
                            # 如果当前选中该节点，刷新 Detail Pane
                            current_selection = self.tree_view.selectionModel().selectedIndexes()
                            if current_selection:
                                selected_index = self.proxy_model.mapToSource(current_selection[0])
                                selected_node = selected_index.internalPointer()
                                if selected_node and selected_node.data.get('id') == entry_id:
                                    self._render_detail(node.data)
                            break
            else:
                error_msg = stderr if stderr else "Unknown error"
                QMessageBox.warning(self, "警告", f"签名验证失败: {error_msg}")
                
                # 写回错误状态
                entry_id = data.get('id')
                if entry_id:
                    for node in self.model.root_nodes:
                        if node.data.get('id') == entry_id:
                            node.data['signer_status'] = "(Error)"
                            node.data['signature_detail'] = error_msg
                            # 更新 detail_data
                            if 'detail_data' in node.data:
                                node.data['detail_data']['signature'] = "Error"
                            # 刷新缓存并更新 UI
                            self.model.refresh_node(node)
                            self.model.emit_node_changed(node)
                            break
        except subprocess.TimeoutExpired:
            error_msg = "签名验证超时"
            QMessageBox.critical(self, "错误", error_msg)
            
            # 写回错误状态
            entry_id = data.get('id')
            if entry_id:
                for node in self.model.root_nodes:
                    if node.data.get('id') == entry_id:
                        node.data['signer_status'] = "(Error)"
                        node.data['signature_detail'] = error_msg
                        # 更新 detail_data
                        if 'detail_data' in node.data:
                            node.data['detail_data']['signature'] = "Error"
                        # 刷新缓存并更新 UI
                        self.model.refresh_node(node)
                        self.model.emit_node_changed(node)
                        break
        except Exception as e:
            error_msg = str(e)
            QMessageBox.critical(self, "错误", f"签名验证失败: {error_msg}")
            
            # 写回错误状态
            entry_id = data.get('id')
            if entry_id:
                for node in self.model.root_nodes:
                    if node.data.get('id') == entry_id:
                        node.data['signer_status'] = "(Error)"
                        node.data['signature_detail'] = error_msg
                        # 更新 detail_data
                        if 'detail_data' in node.data:
                            node.data['detail_data']['signature'] = "Error"
                        # 刷新缓存并更新 UI
                        self.model.refresh_node(node)
                        self.model.emit_node_changed(node)
                        break
    
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
            
            # 首先尝试同时匹配 entry 和 location
            if target_location:
                for i in range(source_model.rowCount()):
                    index = source_model.index(i, 0)
                    node = index.internalPointer()
                    if node:
                        node_entry = node.data.get('entry', '')
                        node_location = node.data.get('location', '')
                        if node_entry == target_entry and node_location == target_location:
                            proxy_index = proxy_model.mapFromSource(index)
                            if proxy_index.isValid():
                                view.setCurrentIndex(proxy_index)
                                view.scrollTo(proxy_index)
                            return
            
            # 如果 location 为空或精确匹配失败，则只匹配 entry
            for i in range(source_model.rowCount()):
                index = source_model.index(i, 0)
                node = index.internalPointer()
                if node and node.data.get('entry') == target_entry:
                    proxy_index = proxy_model.mapFromSource(index)
                    if proxy_index.isValid():
                        view.setCurrentIndex(proxy_index)
                        view.scrollTo(proxy_index)
                    return
        except Exception as e:
            QMessageBox.warning(self, "错误", f"跳转失败: {str(e)}")


    def _on_scan_error(self, error_msg):
        """扫描错误处理"""
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("开始扫描")
        self.btn_cancel.setEnabled(False)  # Disable cancel button
        self._is_scanning = False
        
        # Update status bar
        self.lbl_scan_status.setText(f"错误: {error_msg}")
        if self._scan_start_time:
            elapsed = int(time.time() - self._scan_start_time)
            self.lbl_scan_duration.setText(f"耗时: {elapsed}秒")
        
        # 清空 Detail Pane
        self._clear_detail_layout()
        self.detail_placeholder = QLabel("Select an entry to view details")
        self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
        self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
        self.current_entry_id = None
        
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
                
                # 获取源模型中的行号
                source_row = source_index.row()
                
                # 获取原始数据中的对应项
                if source_row < len(self.current_data):
                    entry_dict = self.current_data[source_row]
                    
                    # 创建AutorunEntry对象
                    from core.autoruns_parser import AutorunEntry
                    entry = AutorunEntry(**entry_dict)
                    
                    # 尝试删除
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
        print(f"[DeleteEntry] 开始删除条目")
        
        entry_name = data.get('entry', '')
        category = data.get('category', '')
        launch_string = data.get('launch_string', '')
        image_path = data.get('image_path', '')
        service_name = data.get('service_name', '')
        
        print(f"[DeleteEntry] 条目信息:")
        print(f"  - entry_name: {entry_name}")
        print(f"  - category: {category}")
        print(f"  - launch_string: {launch_string}")
        print(f"  - image_path: {image_path}")
        print(f"  - service_name: {service_name}")
        
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
            print(f"[DeleteEntry] 用户取消删除")
            return
        
        try:
            print(f"[DeleteEntry] 创建 AutorunEntry 对象")
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
            
            print(f"[DeleteEntry] AutorunEntry 对象创建完成")
            print(f"[DeleteEntry] 调用 parser.delete_entry")
            
            # 根据类型删除
            success, message = self.parser.delete_entry(entry)
            
            print(f"[DeleteEntry] 删除结果: success={success}, message={message}")
            
            if success:
                QMessageBox.information(self, "删除成功", message)
                
                print(f"[DeleteEntry] 从模型中移除条目")
                # 从模型中移除该条目
                entry_id = data.get('id')
                for i, node in enumerate(self.model.root_nodes):
                    if node.data.get('id') == entry_id:
                        print(f"[DeleteEntry] 找到条目，索引: {i}")
                        self.model.beginRemoveRows(QModelIndex(), i, i)
                        self.model.root_nodes.pop(i)
                        self.model.endRemoveRows()
                        print(f"[DeleteEntry] 条目已从模型中移除")
                        break
                
                print(f"[DeleteEntry] 清空 Detail Pane")
                # 清空 Detail Pane
                self._clear_detail_layout()
                self.detail_placeholder = QLabel("Select an entry to view details")
                self.detail_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.detail_placeholder.setStyleSheet("color: #999; font-style: italic;")
                self.detail_layout.addWidget(self.detail_placeholder, 0, 0, 1, 2)
                self.current_entry_id = None
            else:
                print(f"[DeleteEntry] 删除失败")
                QMessageBox.warning(self, "删除失败", f"删除失败: {message}")
                
        except Exception as e:
            import traceback
            print(f"[DeleteEntry] 删除过程中发生错误: {e}")
            print(f"[DeleteEntry] 错误堆栈:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "删除错误", f"删除过程中发生错误: {str(e)}")
    
    def _copy_and_encrypt_file(self, data):
        """复制文件并加密压缩
        
        DEPRECATED: 此方法已废弃，请使用工作台的加密压缩功能
        工作台支持统一路径选择（self / directory / parent）和命令预览
        """
        import os
        import pyzipper
        from datetime import datetime
        
        image_path = data.get('image_path', '')
        entry_name = data.get('entry', '')
        
        # 校验文件是否存在
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self, "警告", "文件不存在，无法复制")
            return
        
        try:
            # 获取 SHA256 前三位
            sha256 = data.get('sha256', '')
            sha256_prefix = sha256[:3] if sha256 else '000'
            
            # 压缩包命名规则：<entry_name>_<sha256前三位>.zip
            zip_filename = f"{entry_name}_{sha256_prefix}.zip"
            
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
            
        except PermissionError:
            QMessageBox.critical(self, "错误", "权限不足，无法访问文件")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"压缩过程中发生错误: {str(e)}")
    
    def _export_csv(self):
        """导出CSV"""
        # 实现导出逻辑...
        pass

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
        content_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
                line-height: 1.6;
            }
        """)

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
<p style="color: #b8860b;">UI 表现：浅黄色背景，深金色字体，图标右下角黄色标记</p>

<p><b>🔴 高风险 (HIGH_RISK)</b></p>
<ul>
<li>文件不存在 (已被删除或移动)</li>
<li>无签名 + 位于用户可写目录 (AppData / Temp / Downloads 等)</li>
<li>典型的恶意软件驻留路径</li>
</ul>
<p style="color: #8b0000;">UI 表现：浅红色背景，深红色字体，图标右下角红色标记</p>

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
