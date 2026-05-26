from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QLabel,
    QMessageBox, QHeaderView, QLineEdit, QFrame,
    QGridLayout, QMenu, QFileDialog, QApplication,
    QSplitter, QTextEdit, QSizePolicy, QCheckBox,
    QDialog, QDialogButtonBox, QScrollArea, QSpinBox,
    QToolTip
)
from PyQt6.QtCore import Qt, QTimer, QSortFilterProxyModel, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from datetime import datetime
import json
import os
import subprocess
import webbrowser

import logging

from core.sysmon import (
    SysmonSubscriber, SysmonConfigManager,
    DnsEvent, SysmonEvent, NetworkConnectEvent, CreateRemoteThreadEvent, FileCreateEvent
)
from core.sysmon.config_manager import EVENT_CONFIG, DEFAULT_ENABLED_EVENTS
from ui.table_model import HighPerformanceTableModel
from ui.ui_style import apply_flat_style, ensure_close_svg, ensure_expand_svg
from ui.process_tree_widget import ProcessTreeWidget
from ui.dropdown_button import DropdownButton

logger = logging.getLogger('IRtool')


EVENT_COLUMNS = [
    "时间", "事件类型", "事件ID", "进程名", "PID/源PID", "目标进程", "详情", "用户", "进程路径"
]


class EventTableModel(HighPerformanceTableModel):
    def __init__(self, parent=None):
        super().__init__(EVENT_COLUMNS, parent)

    def lessThan(self, left, right):
        left_val = self.data(left, Qt.ItemDataRole.EditRole)
        right_val = self.data(right, Qt.ItemDataRole.EditRole)
        try:
            return float(left_val) < float(right_val)
        except (TypeError, ValueError):
            return str(left_val) < str(right_val)


class EventFilterProxyModel(QSortFilterProxyModel):
    """自定义过滤代理模型，支持事件类型和外连IP筛选"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._event_type_filter = "全部"
        self._external_only = False
        self._events_data = []  # 存储事件对象引用
        self._search_text = ""
        self._process_text = ""

    def set_event_type_filter(self, event_type: str):
        self._event_type_filter = event_type
        self.invalidateFilter()

    def set_external_only(self, external_only: bool):
        self._external_only = external_only
        self.invalidateFilter()

    def set_events_data(self, events: list):
        self._events_data = events
        self.invalidateFilter()

    def set_text_filters(self, search_text: str, process_text: str):
        """设置双文本过滤条件，两者均需满足（AND 逻辑）"""
        self._search_text = search_text
        self._process_text = process_text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        # 双文本 AND 过滤：在调用父类之前先检查自定义文本条件
        if self._search_text or self._process_text:
            source_model = self.sourceModel()
            col_count = source_model.columnCount()
            row_text = " ".join(
                str(source_model.index(source_row, col, source_parent).data() or "")
                for col in range(col_count)
            ).lower()
            if self._search_text and self._search_text not in row_text:
                return False
            if self._process_text and self._process_text not in row_text:
                return False

        # 获取对应的事件对象
        if source_row < 0 or source_row >= len(self._events_data):
            return True

        event = self._events_data[source_row]

        # 事件类型筛选
        if self._event_type_filter != "全部":
            event_type_eid_map = {
                "进程创建": 1,
                "文件创建时间修改": 2,
                "网络连接": 3,
                "进程终止": 5,
                "驱动加载": 6,
                "DLL加载": 7,
                "远程线程创建": 8,
                "原始磁盘访问": 9,
                "进程访问": 10,
                "文件创建": 11,
                "DLL文件创建": 11,
                "注册表事件": 12,
                "文件流哈希": 15,
                "管道事件": 17,
                "WMI事件": 19,
                "DNS查询": 22,
                "文件删除": 23,
                "剪贴板变化": 24,
                "进程篡改": 25,
                "文件删除检测": 26,
            }
            target_eid = event_type_eid_map.get(self._event_type_filter)
            if target_eid is not None:
                if self._event_type_filter == "DLL文件创建":
                    if not (isinstance(event, FileCreateEvent) and
                            getattr(event, 'target_filename', '').lower().endswith('.dll')):
                        return False
                elif self._event_type_filter == "注册表事件":
                    if event.event_id not in (12, 13, 14):
                        return False
                elif self._event_type_filter == "管道事件":
                    if event.event_id not in (17, 18):
                        return False
                elif self._event_type_filter == "WMI事件":
                    if event.event_id not in (19, 20, 21):
                        return False
                elif event.event_id != target_eid:
                    return False

        # 仅外连筛选（包括外连IP的网络连接和DNS查询）
        if self._external_only:
            is_external_connection = False
            if isinstance(event, NetworkConnectEvent):
                is_external_connection = event.is_external
            elif isinstance(event, DnsEvent):
                # DNS查询算作外连
                is_external_connection = True
            
            if not is_external_connection:
                return False

        return True


class HistoryLoadWorker(QThread):
    """后台线程：加载历史 Sysmon 事件，避免阻塞主线程 UI"""
    finished = pyqtSignal(list)

    def __init__(self, subscriber, limit, filter_external):
        super().__init__()
        self._subscriber = subscriber
        self._limit = limit
        self._filter_external = filter_external

    def run(self):
        events = self._subscriber.get_existing_events(
            limit=self._limit, filter_external_only=self._filter_external
        )
        self.finished.emit(events)


class SysmonActionWorker(QThread):
    """后台线程：执行 Sysmon 安装/卸载/配置更新，避免阻塞主线程 UI"""
    finished = pyqtSignal(bool, str)

    def __init__(self, action, config_manager):
        super().__init__()
        self._action = action
        self._config_manager = config_manager

    def run(self):
        try:
            if self._action == 'install':
                success, msg = self._config_manager.install()
            elif self._action == 'uninstall':
                success, msg = self._config_manager.uninstall()
            elif self._action == 'update_config':
                success, msg = self._config_manager.update_config()
            else:
                success, msg = False, f"未知操作: {self._action}"
            self.finished.emit(success, msg)
        except Exception as e:
            self.finished.emit(False, str(e))


_ALL_SYSMON_EVENTS = [
    ('network', '网络连接', 'EventID 3 — 监控进程的网络连接活动，记录源/目标IP、端口和协议。应急响应核心数据源，用于追踪C2通信、横向移动、数据外泄'),
    ('dns', 'DNS查询', 'EventID 22 — 记录进程发起的DNS查询域名。应急响应核心数据源，用于发现恶意域名解析、DGA域名、隧道通信'),
    ('remote_thread', '远程线程创建', 'EventID 8 — 检测跨进程注入线程的行为。应急响应关键指标，用于发现代码注入、恶意软件持久化'),
    ('process_create', '进程创建', 'EventID 1 — 记录新进程创建，含命令行、父进程等信息。应急响应核心数据源，用于追踪攻击链和恶意执行'),
    ('process_terminate', '进程终止', 'EventID 5 — 记录进程退出事件。辅助分析进程生命周期和异常终止'),
    ('file_create', '文件创建', 'EventID 11 — 记录文件创建事件。可用于监控敏感目录文件写入、恶意文件释放'),
    ('file_create_dll', 'DLL文件创建', 'EventID 11 — 仅记录.dll文件的创建。监控DLL侧加载和恶意DLL释放，数据量比完整文件创建小'),
    ('registry_event', '注册表事件', 'EventID 12/13/14 — 监控注册表创建、修改和删除。用于检测持久化机制（自启动项、COM劫持等）'),
    ('process_access', '进程访问', 'EventID 10 — 记录进程间读写内存操作。检测凭据窃取（如lsass内存读取）和进程 hollowing'),
    ('driver_load', '驱动加载', 'EventID 6 — 记录内核驱动加载事件。检测Rootkit和恶意驱动安装'),
    ('image_load', 'DLL加载', 'EventID 7 — 记录进程加载DLL事件。数据量较大，用于检测DLL侧加载和可疑模块注入'),
    ('raw_access_read', '原始磁盘访问', 'EventID 9 — 检测进程绕过文件系统直接读取磁盘。用于发现磁盘窃取、勒索软件行为'),
    ('file_create_stream_hash', '文件流哈希', 'EventID 15 — 记录文件备用数据流的哈希。检测NTFS ADS隐藏恶意代码'),
    ('pipe_event', '管道事件', 'EventID 17/18 — 监控命名管道的创建和连接。检测SMB横向移动和命名管道 impersonation'),
    ('wmi_event', 'WMI事件', 'EventID 19/20/21 — 监控WMI事件订阅和消费者。检测WMI持久化机制（无文件攻击）'),
    ('file_delete', '文件删除', 'EventID 23 — 记录文件删除事件。检测日志清理、勒索软件加密后删除原文件'),
    ('clipboard_change', '剪贴板变化', 'EventID 24 — 监控剪贴板内容变化。检测剪贴板窃取（如窃取密码、加密货币地址替换）'),
    ('process_tampering', '进程篡改', 'EventID 25 — 检测进程内存被篡改（如Process Hollowing）。高级攻击手法检测'),
    ('file_delete_detected', '文件删除检测', 'EventID 26 — 与文件删除类似但记录方式不同，用于检测关键文件被删除'),
    ('file_create_time', '文件创建时间修改', 'EventID 2 — 检测文件时间戳篡改（Timestomping）。攻击者常用技术隐藏恶意文件真实创建时间'),
]

_EVENT_DISPLAY_NAMES = {
    'network': '网络连接',
    'dns': 'DNS查询',
    'remote_thread': '远程线程创建',
    'process_create': '进程创建',
    'process_terminate': '进程终止',
    'file_create': '文件创建',
    'file_create_dll': 'DLL文件创建',
    'registry_event': '注册表事件',
    'process_access': '进程访问',
    'driver_load': '驱动加载',
    'image_load': 'DLL加载',
    'raw_access_read': '原始磁盘访问',
    'file_create_stream_hash': '文件流哈希',
    'pipe_event': '管道事件',
    'wmi_event': 'WMI事件',
    'file_delete': '文件删除',
    'clipboard_change': '剪贴板变化',
    'process_tampering': '进程篡改',
    'file_delete_detected': '文件删除检测',
    'file_create_time': '文件创建时间修改',
}

_XML_TAG_MAP = {
    'network': 'NetworkConnect',
    'dns': 'DnsQuery',
    'remote_thread': 'CreateRemoteThread',
    'process_create': 'ProcessCreate',
    'process_terminate': 'ProcessTerminate',
    'file_create': 'FileCreate',
    'file_create_dll': 'FileCreate',
    'registry_event': 'RegistryEvent',
    'process_access': 'ProcessAccess',
    'driver_load': 'DriverLoad',
    'image_load': 'ImageLoad',
    'raw_access_read': 'RawAccessRead',
    'file_create_stream_hash': 'FileCreateStreamHash',
    'pipe_event': 'PipeEvent',
    'wmi_event': 'WmiEvent',
    'file_delete': 'FileDelete',
    'clipboard_change': 'ClipboardChange',
    'process_tampering': 'ProcessTampering',
    'file_delete_detected': 'FileDeleteDetected',
    'file_create_time': 'FileCreateTime',
}


class SysmonConfigDialog(QDialog):
    _DIALOG_STYLE = """
    QDialog { background-color: #f5f6f8; }
    QLabel { color: #2b2f33; background: transparent; }
    QCheckBox { spacing: 6px; color: #3a3f47; background: transparent; }
    QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1.5px solid #c0c6d0; background-color: #ffffff; }
    QCheckBox::indicator:checked { background-color: #4c8dff; border-color: #4c8dff; }
    QCheckBox::indicator:hover { border-color: #4c8dff; }
    QPushButton { background-color: #ffffff; border: 1px solid #d0d6e0; border-radius: 5px; padding: 5px 14px; font-weight: 500; color: #3a3f47; }
    QPushButton:hover { background-color: #f0f4ff; border-color: #b8c8e8; color: #1a5fbf; }
    QPushButton:pressed { background-color: #dceaff; border-color: #4c8dff; }
    QPushButton:disabled { background-color: #f5f6f8; color: #b0b5bd; border-color: #e4e8ee; }
    QScrollArea { background: transparent; border: none; }
    QScrollBar:vertical { background: transparent; width: 8px; margin: 0px; }
    QScrollBar::handle:vertical { background: #cdd3dc; min-height: 30px; border-radius: 4px; }
    QScrollBar::handle:vertical:hover { background: #a8b0bc; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QToolTip { background-color: #ffffff; color: #2b2f33; border: 1px solid #dce1e8; border-radius: 4px; padding: 5px 8px; font-size: 12px; }
    """

    def __init__(self, current_enabled, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._DIALOG_STYLE)
        tip_palette = QPalette()
        tip_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
        tip_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#2b2f33"))
        QToolTip.setPalette(tip_palette)
        self.setWindowTitle("调整 Sysmon 采集配置")
        self.setMinimumWidth(520)
        self._result = None
        self._checkboxes = {}
        self._init_ui(current_enabled)

    def _init_ui(self, current_enabled):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        hint = QLabel("勾选需要启用的事件类型，应用后将更新 Sysmon 配置文件并重新加载。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 12px; padding: 0 4px;")
        layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)

        row = 0
        for key, name, desc in _ALL_SYSMON_EVENTS:
            cb = QCheckBox(name)
            cb.setChecked(key in current_enabled)
            cb.setToolTip(desc)
            cb.setStyleSheet("QCheckBox { font-weight: 500; }")
            self._checkboxes[key] = cb

            desc_label = QLabel(desc.split('—')[0].strip() if '—' in desc else '')
            desc_label.setStyleSheet("color: #8b8f96; font-size: 11px; padding-left: 2px;")
            desc_label.setToolTip(desc)

            grid.addWidget(cb, row, 0)
            grid.addWidget(desc_label, row, 1)
            row += 1

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("应用配置")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)

        btn_select_all = QPushButton("全选")
        btn_select_all.clicked.connect(self._on_select_all)
        btn_deselect_all = QPushButton("取消全选")
        btn_deselect_all.clicked.connect(self._on_deselect_all)
        btn_box.addButton(btn_select_all, QDialogButtonBox.ButtonRole.ActionRole)
        btn_box.addButton(btn_deselect_all, QDialogButtonBox.ButtonRole.ActionRole)

        layout.addWidget(btn_box)

    def _on_accept(self):
        self._result = [key for key, cb in self._checkboxes.items() if cb.isChecked()]
        self.accept()

    def _on_select_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def _on_deselect_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)

    def get_result(self):
        return self._result


class LogCollectorTab(QWidget):

    def __init__(self, data_store=None):
        super().__init__()
        apply_flat_style(self)

        self.data_store = data_store
        self.subscriber = None
        self.config_manager = SysmonConfigManager()

        self.all_events = []
        self._is_collecting = False
        self._start_time = None
        self._sysmon_was_started_by_us = False
        self._enabled_events = list(DEFAULT_ENABLED_EVENTS)

        self._init_ui()
        self._check_crash_recovery()
        self._update_status_display()

        self._pending_events = []
        self._batch_update_timer = QTimer()
        self._batch_update_timer.setSingleShot(True)
        self._batch_update_timer.timeout.connect(self._flush_batch_update)
        self._history_load_worker = None
        self._sysmon_action_worker = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_start = QPushButton("▶ 启动采集")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.clicked.connect(self._toggle_collection)

        self.btn_deploy = QPushButton("部署 Sysmon")
        self.btn_deploy.clicked.connect(self._deploy_sysmon)

        self.btn_uninstall = QPushButton("卸载 Sysmon")
        self.btn_uninstall.setProperty("class", "danger")
        self.btn_uninstall.setEnabled(False)
        self.btn_uninstall.clicked.connect(self._uninstall_sysmon)

        self.btn_load_history = QPushButton("加载历史")
        self.btn_load_history.clicked.connect(self._load_history_events)

        self.btn_clear = QPushButton("清空记录")
        self.btn_clear.setProperty("class", "danger")
        self.btn_clear.clicked.connect(self._clear_events)

        self.btn_export = QPushButton("↓ 导出")
        self.btn_export.clicked.connect(self._export_events)

        toolbar.addWidget(self.btn_start)
        toolbar.addWidget(self.btn_deploy)
        toolbar.addWidget(self.btn_uninstall)
        toolbar.addWidget(self.btn_load_history)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_export)
        toolbar.addStretch()

        self.lbl_log_size = QLabel("日志大小: --")
        self.lbl_log_size.setToolTip("Sysmon 事件日志最大大小（通过 wevtutil 读取）")
        self.lbl_log_size.setStyleSheet("color: #6b7280; font-size: 12px;")
        toolbar.addWidget(self.lbl_log_size)

        self.spin_log_size = QSpinBox()
        self.spin_log_size.setRange(1, 4096)
        self.spin_log_size.setSuffix(" MB")
        self.spin_log_size.setToolTip("设置 Sysmon 事件日志最大大小（需管理员权限写入）")
        self.spin_log_size.setFixedWidth(90)
        self.spin_log_size.setStyleSheet("QSpinBox { padding: 2px 4px; font-size: 12px; }")
        toolbar.addWidget(self.spin_log_size)

        self.btn_set_log_size = QPushButton("应用")
        self.btn_set_log_size.setToolTip("将日志大小设置应用到系统")
        self.btn_set_log_size.clicked.connect(self._on_set_log_size)
        toolbar.addWidget(self.btn_set_log_size)

        self.chk_external_only = QCheckBox("仅外连")
        self.chk_external_only.setToolTip("只显示外连事件（外网IP的网络连接和DNS查询）")
        self.chk_external_only.stateChanged.connect(self._on_external_only_changed)
        toolbar.addWidget(self.chk_external_only)

        layout.addLayout(toolbar)

        config_frame = QFrame()
        config_frame.setFrameShape(QFrame.Shape.StyledPanel)
        config_frame.setObjectName("panel")
        config_layout = QHBoxLayout(config_frame)
        config_layout.setContentsMargins(10, 4, 10, 4)

        config_layout.addWidget(QLabel("采集配置:"))

        self.btn_adjust_config = QPushButton("调整配置")
        self.btn_adjust_config.setToolTip("打开配置对话框，选择需要启用的 Sysmon 事件类型")
        self.btn_adjust_config.clicked.connect(self._on_adjust_config)
        config_layout.addWidget(self.btn_adjust_config)

        self.btn_open_config = QPushButton("打开配置文件")
        self.btn_open_config.setToolTip("打开配置文件所在目录")
        self.btn_open_config.clicked.connect(self._open_config_location)
        config_layout.addWidget(self.btn_open_config)

        config_layout.addStretch()
        layout.addWidget(config_frame)

        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.NoFrame)
        status_frame.setObjectName("stats-bar")
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(10, 5, 10, 5)

        self.lbl_status_icon = QLabel("●")
        self.lbl_status_icon.setStyleSheet("color: gray; font-size: 16px;")

        self.lbl_status = QLabel("状态: 未连接")
        self.lbl_events_count = QLabel("事件数: 0")
        self.lbl_duration = QLabel("采集时长: --:--:--")
        self.lbl_sysmon_status = QLabel("Sysmon: 检测中...")

        status_layout.addWidget(self.lbl_status_icon, 0, 0)
        status_layout.addWidget(self.lbl_status, 0, 1)
        status_layout.addWidget(self.lbl_events_count, 0, 2)
        status_layout.addWidget(self.lbl_duration, 0, 3)
        status_layout.addWidget(self.lbl_sysmon_status, 0, 4)

        layout.addWidget(status_frame)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("事件类型:"))
        self.event_type_filter = DropdownButton()
        self._update_event_type_filter()
        self.event_type_filter.currentTextChanged.connect(self._on_event_type_changed)
        filter_layout.addWidget(self.event_type_filter)

        filter_layout.addWidget(QLabel("搜索:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("域名/进程名/进程路径/PID")
        self.search_box.textChanged.connect(self._on_search_text_changed)
        filter_layout.addWidget(self.search_box, 1)

        filter_layout.addWidget(QLabel("进程筛选:"))
        self.process_filter = QLineEdit()
        self.process_filter.setPlaceholderText("进程名包含...")
        self.process_filter.textChanged.connect(self._on_search_text_changed)
        filter_layout.addWidget(self.process_filter, 1)

        layout.addLayout(filter_layout)

        self._model = EventTableModel(self)
        self._proxy_model = EventFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setSortRole(Qt.ItemDataRole.EditRole)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableView()
        self.table.setModel(self._proxy_model)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)

        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.table.doubleClicked.connect(self._on_double_click)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        splitter.addWidget(self.table)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)

        self._detail_close_btn = QPushButton()
        self._detail_close_btn.setFixedSize(24, 24)
        self._detail_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._detail_close_btn.setToolTip("关闭详情面板")
        close_svg = ensure_close_svg()
        close_style = (
            "QPushButton { border: 1px solid #c0c6d0; background: #f0f2f5; border-radius: 4px; padding: 0px; }"
            "QPushButton:hover { background: #e0e4ea; border: 1px solid #a0a8b4; }"
            "QPushButton:pressed { background: #d0d4da; }"
        )
        if close_svg:
            close_style += f"QPushButton {{ image: url({close_svg.replace(chr(92), '/')}); }}"
        self._detail_close_btn.setStyleSheet(close_style)
        self._detail_close_btn.clicked.connect(self._close_detail_panels)

        detail_header = QHBoxLayout()
        detail_header.setContentsMargins(0, 0, 4, 0)
        detail_header.addStretch()
        detail_header.addWidget(self._detail_close_btn)

        self._detail_panel = QTextEdit()
        self._detail_panel.setReadOnly(True)
        self._detail_panel.setPlaceholderText("点击事件行查看详细信息...")
        self._detail_panel.setStyleSheet(
            "QTextEdit { background-color: #f8f8f8; border: 1px solid #ddd; "
            "border-radius: 4px; padding: 8px; font-family: 'Microsoft YaHei', 'Consolas', monospace; font-size: 13px; }"
        )
        self._detail_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._detail_panel.setMinimumHeight(80)
        self._detail_panel.setMaximumHeight(300)

        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self._detail_panel)
        detail_container.hide()

        splitter.addWidget(detail_container)
        self._detail_container = detail_container

        self._process_tree_widget = ProcessTreeWidget()
        self._process_tree_widget.setMinimumHeight(80)
        self._process_tree_widget.setMaximumHeight(220)
        self._process_tree_widget.hide()
        splitter.addWidget(self._process_tree_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter)

        self._btn_expand_detail = QPushButton()
        self._btn_expand_detail.setFixedSize(24, 24)
        self._btn_expand_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_expand_detail.setToolTip("展开事件详情和进程链")
        expand_svg = ensure_expand_svg()
        expand_style = (
            "QPushButton { border: 1px solid #c0c6d0; background: #f0f2f5; border-radius: 4px; padding: 0px; }"
            "QPushButton:hover { background: #e0e4ea; border: 1px solid #a0a8b4; }"
            "QPushButton:pressed { background: #d0d4da; }"
        )
        if expand_svg:
            expand_style += f"QPushButton {{ image: url({expand_svg.replace(chr(92), '/')}); }}"
        self._btn_expand_detail.setStyleSheet(expand_style)
        self._btn_expand_detail.clicked.connect(self._expand_detail_panels)
        self._btn_expand_detail.hide()
        self._btn_expand_detail.setParent(self)

        self.duration_timer = QTimer()
        self.duration_timer.timeout.connect(self._update_duration)

        self._search_debounce_timer = QTimer()
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._apply_filters)

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_auto_resize)

    def _on_search_text_changed(self):
        self._search_debounce_timer.start(300)

    def _do_auto_resize(self):
        self.table.resizeColumnsToContents()

    def _update_status_display(self):
        info = self.config_manager.get_status_info()

        if info['installed']:
            if info['running']:
                label = f"Sysmon: 运行中 ({info['service_name']})"
                if info.get('config_managed_by_irtool'):
                    label += " [IRtool配置]"
                elif info.get('started_by_irtool'):
                    label += " [由本软件启动]"
                self.lbl_sysmon_status.setText(label)
                self.lbl_sysmon_status.setStyleSheet("color: green;")
            else:
                label = "Sysmon: 已安装但未运行"
                if info.get('config_managed_by_irtool'):
                    label += " [IRtool配置]"
                self.lbl_sysmon_status.setText(label)
                self.lbl_sysmon_status.setStyleSheet("color: orange;")
        else:
            self.lbl_sysmon_status.setText("Sysmon: 未安装")
            self.lbl_sysmon_status.setStyleSheet("color: red;")

        if not info['sysmon_exe_exists']:
            self.btn_deploy.setEnabled(False)
            self.btn_deploy.setToolTip(f"找不到 sysmon64.exe\n路径: {info['sysmon_exe_path']}")
        else:
            self.btn_deploy.setEnabled(True)
            self.btn_deploy.setToolTip("")

        if info['installed']:
            self.btn_uninstall.setEnabled(True)
            if info.get('started_by_irtool'):
                self.btn_uninstall.setToolTip("卸载 Sysmon（由本工具安装）")
            else:
                self.btn_uninstall.setToolTip("卸载 Sysmon（非本工具安装，请确认后再卸载）")
        else:
            self.btn_uninstall.setEnabled(False)
            self.btn_uninstall.setToolTip("Sysmon 未安装")

        if info['installed'] and info['running']:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("启动采集")
        elif info['installed'] and not info['running']:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("启动采集 (需启动Sysmon)")

        if info['installed']:
            self._refresh_log_size()
        else:
            self.lbl_log_size.setText("日志大小: --")
            self.spin_log_size.setEnabled(False)
            self.btn_set_log_size.setEnabled(False)

    def _toggle_collection(self):
        if self._is_collecting:
            self._stop_collection()
        else:
            self._start_collection()

    def _start_collection(self):
        logger.info("[LogCollector] 开始启动采集...")
        # 检查是否已安装
        if not self.config_manager.is_installed():
            reply = QMessageBox.question(
                self,
                "需要安装 Sysmon",
                "Sysmon 尚未安装，是否安装并启动采集？\n\n"
                "Sysmon 是微软系统监控工具，用于采集网络连接、DNS查询等安全事件。\n"
                "注意：退出软件时不会自动卸载 Sysmon。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                success, msg = self.config_manager.install()
                if not success:
                    logger.error(f"[LogCollector] Sysmon安装失败: {msg}")
                    QMessageBox.warning(self, "安装失败", msg)
                    return
                self._sysmon_was_started_by_us = True
                self._update_status_display()
            else:
                logger.info("[LogCollector] 用户取消安装Sysmon，采集未启动")
                return
        # 已安装但未运行
        elif not self.config_manager.is_running():
            reply = QMessageBox.question(
                self,
                "Sysmon 未运行",
                "Sysmon 服务未运行，是否立即启动？\n\n"
                "注意：退出软件时会自动停止 Sysmon 服务。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 已安装的情况下，尝试启动服务
                success, msg = self.config_manager.start_service()
                if not success:
                    logger.error(f"[LogCollector] Sysmon服务启动失败: {msg}")
                    QMessageBox.warning(self, "启动失败", msg)
                    return
                self._sysmon_was_started_by_us = True
                self._update_status_display()
            else:
                logger.info("[LogCollector] 用户取消启动Sysmon服务，采集未启动")
                return
        else:
            self._sysmon_was_started_by_us = True
            self.config_manager.mark_started_by_irtool()

        filter_external = self.chk_external_only.isChecked()
        self.subscriber = SysmonSubscriber(filter_external_only=filter_external, enabled_events=self._enabled_events)

        if not self.subscriber.is_sysmon_available():
            logger.error("[LogCollector] Sysmon日志通道不可用，采集启动失败")
            QMessageBox.warning(
                self,
                "无法连接",
                "无法连接到 Sysmon 日志通道。\n请确认 Sysmon 已正确安装。"
            )
            self.subscriber = None
            return

        self.subscriber.events_batch_received.connect(self._on_events_batch_received)
        self.subscriber.status_changed.connect(self._on_status_changed)
        self.subscriber.error_occurred.connect(self._on_error)

        self.subscriber.start()
        logger.info("[LogCollector] 采集已启动")

        self._is_collecting = True
        self._start_time = datetime.now()
        self.duration_timer.start(1000)

        self.btn_start.setText("■ 停止采集")
        self.btn_start.setProperty("class", "danger")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

    def _stop_collection(self):
        if self.subscriber:
            self.subscriber.stop()
            self.subscriber = None

        # 停止 Sysmon 服务（真正暂停采集）
        if self.config_manager.is_running():
            success, msg = self.config_manager.stop_service()
            if not success:
                logger.warning(f"[LogCollector] 停止Sysmon服务失败: {msg}")
            else:
                logger.info("[LogCollector] Sysmon服务已停止")

        self._is_collecting = False
        self._start_time = None
        self.duration_timer.stop()

        self.btn_start.setText("▶ 启动采集")
        self.btn_start.setProperty("class", "primary")
        self.btn_start.style().unpolish(self.btn_start)
        self.btn_start.style().polish(self.btn_start)

        self._update_status_label("disconnected")
        self._update_status_display()

    def _on_events_batch_received(self, events: list):
        for event in events:
            self.all_events.append(event)
            if self.data_store:
                self.data_store.add_sysmon_event(event)
            self._pending_events.append(event)

        if self._pending_events and not self._batch_update_timer.isActive():
            self._batch_update_timer.start(200)

        self.lbl_events_count.setText(f"事件数: {len(self.all_events)}")

    def _on_event_received(self, event):
        """兼容单个事件信号（保留用于向后兼容）"""
        self.all_events.append(event)

        if self.data_store:
            self.data_store.add_sysmon_event(event)

        self._pending_events.append(event)
        if not self._batch_update_timer.isActive():
            self._batch_update_timer.start(200)

        self.lbl_events_count.setText(f"事件数: {len(self.all_events)}")

    def _flush_batch_update(self):
        if not self._pending_events:
            return

        new_rows = []
        new_sort_vals = []
        for event in self._pending_events:
            row, sort_row = self._event_to_row(event)
            new_rows.append(row)
            new_sort_vals.append(sort_row)

        old_model_count = self._model.rowCount()
        self._model.append_rows(new_rows, sort_values=new_sort_vals)
        new_model_count = self._model.rowCount()

        expected_count = old_model_count + len(new_rows)
        trim_count = expected_count - new_model_count
        if trim_count > 0 and len(self.all_events) > new_model_count:
            self.all_events = self.all_events[len(self.all_events) - new_model_count:]

        self._proxy_model.set_events_data(self.all_events)

        pending_count = len(self._pending_events)
        self._pending_events = []

        self._apply_filters()

        if not self._resize_timer.isActive() and self._model.rowCount() <= pending_count + 50:
            self._resize_timer.start(500)

    def _event_to_row(self, event) -> tuple:
        if isinstance(event, DnsEvent):
            display = [
                event.timestamp,
                "DNS查询",
                str(event.event_id),
                event.process_name,
                str(event.process_id),
                "",
                event.query_name,
                event.user,
                event.process_path,
            ]
            sort = [
                event.timestamp_epoch,
                "dns",
                event.event_id,
                event._sort_process_name,
                event.process_id,
                "",
                event._sort_query_name,
                event._sort_user,
                event._sort_process_path,
            ]
        elif isinstance(event, NetworkConnectEvent):
            external_mark = " [外连]" if event.is_external else ""
            display = [
                event.timestamp,
                f"网络连接{external_mark}",
                str(event.event_id),
                event.process_name,
                str(event.process_id),
                "",
                f"{event.source_ip}:{event.source_port} → {event.destination_ip}:{event.destination_port} ({event.protocol})",
                event.user,
                event.process_path,
            ]
            sort = [
                event.timestamp_epoch,
                "network",
                event.event_id,
                event._sort_process_name,
                event.process_id,
                "",
                event._sort_destination,
                event._sort_user,
                event._sort_process_path,
            ]
        elif isinstance(event, CreateRemoteThreadEvent):
            suspicious_mark = " [可疑]" if event.is_suspicious else ""
            display = [
                event.timestamp,
                f"远程线程{suspicious_mark}",
                str(event.event_id),
                event.source_process_name,
                str(event.source_process_id),
                f"{event.target_process_name} (PID:{event.target_process_id})",
                f"线程ID:{event.new_thread_id} 地址:{event.start_address}",
                event.user,
                event.source_process_path,
            ]
            sort = [
                event.timestamp_epoch,
                "remote_thread",
                event.event_id,
                event._sort_source_process_name,
                event.source_process_id,
                event._sort_target_process_name,
                f"{event.new_thread_id} {event.start_address}".lower(),
                event._sort_user,
                event._sort_source_process_path,
            ]
        elif isinstance(event, FileCreateEvent):
            event_type_display = "DLL创建" if event.target_filename.lower().endswith('.dll') else "文件创建"
            display = [
                event.timestamp,
                event_type_display,
                str(event.event_id),
                event.process_name,
                str(event.process_id),
                "",
                event.target_filename,
                event.user,
                event.process_path,
            ]
            sort = [
                event.timestamp_epoch,
                "file_create",
                event.event_id,
                event._sort_process_name,
                event.process_id,
                "",
                event._sort_target_filename,
                event._sort_user,
                event._sort_process_path,
            ]
        else:
            content = str(event.raw_data)[:100] if event.raw_data else ""
            display = [
                event.timestamp,
                "其他",
                str(event.event_id),
                getattr(event, 'process_name', ''),
                str(getattr(event, 'process_id', 0)),
                "",
                content,
                getattr(event, 'user', ''),
                getattr(event, 'process_path', ''),
            ]
            sort = [
                event.timestamp_epoch,
                "other",
                event.event_id,
                getattr(event, 'process_name', '').lower(),
                getattr(event, 'process_id', 0),
                "",
                content.lower(),
                getattr(event, 'user', '').lower(),
                getattr(event, 'process_path', '').lower(),
            ]
        return display, sort

    def _on_status_changed(self, status):
        self._update_status_label(status)

    def _update_status_label(self, status):
        color_map = {
            'connected': ('green', '已连接'),
            'disconnected': ('gray', '已断开'),
            'error': ('red', '错误'),
            'connecting': ('orange', '连接中...'),
        }

        color, text = color_map.get(status, ('gray', status))
        self.lbl_status_icon.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.lbl_status.setText(f"状态: {text}")

    def _on_error(self, error_msg):
        logger.error(f"[LogCollector] 采集错误: {error_msg}")
        QMessageBox.warning(self, "错误", f"日志采集错误:\n{error_msg}")

    def _update_duration(self):
        if self._start_time:
            elapsed = datetime.now() - self._start_time
            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_duration.setText(f"采集时长: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _apply_filters(self):
        search_text = self.search_box.text().strip().lower()
        process_text = self.process_filter.text().strip().lower()

        self._proxy_model.set_text_filters(search_text, process_text)

        # 更新事件数据引用
        self._proxy_model.set_events_data(self.all_events)

    def _on_event_type_changed(self, event_type: str):
        """事件类型筛选改变"""
        self._proxy_model.set_event_type_filter(event_type)
        self._apply_filters()

    def _on_external_only_changed(self, state):
        """仅外连筛选改变"""
        self._proxy_model.set_external_only(state == Qt.CheckState.Checked.value)

    def _update_event_type_filter(self):
        """根据已启用事件更新筛选下拉框"""
        current = self.event_type_filter.currentText()
        self.event_type_filter.blockSignals(True)
        self.event_type_filter.clear()
        self.event_type_filter.addItem("全部")
        for key in self._enabled_events:
            name = _EVENT_DISPLAY_NAMES.get(key)
            if name:
                self.event_type_filter.addItem(name)
        try:
            idx = self.event_type_filter._items.index(current)
            self.event_type_filter.setCurrentIndex(idx)
        except ValueError:
            self.event_type_filter.setCurrentIndex(0)
        self.event_type_filter.blockSignals(False)

    def _on_adjust_config(self):
        """打开配置对话框调整 Sysmon 采集配置"""
        if self._is_collecting:
            QMessageBox.warning(self, "提示", "请先停止采集再修改配置")
            return

        dialog = SysmonConfigDialog(self._enabled_events, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if not result:
                QMessageBox.warning(self, "提示", "至少需要启用一种事件类型")
                return

            success, msg = self.config_manager.apply_config(result)
            if success:
                self._enabled_events = result
                self._update_event_type_filter()
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失败", msg)

    def _on_set_log_size(self):
        """设置 Sysmon 日志最大大小"""
        size_mb = self.spin_log_size.value()
        size_bytes = size_mb * 1024 * 1024
        success, msg = self.config_manager.set_log_max_size(size_bytes)
        if success:
            QMessageBox.information(self, "成功", msg)
            self._refresh_log_size()
        else:
            QMessageBox.warning(self, "失败", msg)

    def _refresh_log_size(self):
        """刷新日志大小显示"""
        size_bytes = self.config_manager.get_log_max_size()
        if size_bytes is not None:
            size_mb = size_bytes // (1024 * 1024)
            self.lbl_log_size.setText(f"日志大小: {size_mb} MB")
            self.spin_log_size.setValue(size_mb)
            self.spin_log_size.setEnabled(True)
            self.btn_set_log_size.setEnabled(True)
        else:
            self.lbl_log_size.setText("日志大小: --")
            self.spin_log_size.setValue(64)
            self.spin_log_size.setEnabled(False)
            self.btn_set_log_size.setEnabled(False)

    def _open_config_location(self):
        """打开配置文件所在目录"""
        config_path = self.config_manager.config_path

        if not config_path.exists():
            # 如果配置文件不存在，创建目录
            config_path.parent.mkdir(parents=True, exist_ok=True)

        # 打开资源管理器并选中配置文件（如果存在）或目录
        if config_path.exists():
            subprocess.run(["explorer", "/select,", str(config_path)], check=False)
        else:
            subprocess.run(["explorer", str(config_path.parent)], check=False)

    def _deploy_sysmon(self):
        info = self.config_manager.get_status_info()

        if self._sysmon_action_worker and self._sysmon_action_worker.isRunning():
            QMessageBox.warning(self, "提示", "Sysmon 操作正在进行中，请稍候")
            return

        if info['installed']:
            reply = QMessageBox.question(
                self,
                "Sysmon 已安装",
                "Sysmon 已安装，是否重新安装/更新配置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            self.btn_deploy.setEnabled(False)
            self.btn_deploy.setText("更新中...")
            self._sysmon_action_worker = SysmonActionWorker('update_config', self.config_manager)
            self._sysmon_action_worker.finished.connect(self._on_deploy_finished)
            self._sysmon_action_worker.start()
        else:
            self.btn_deploy.setEnabled(False)
            self.btn_deploy.setText("安装中...")
            self._sysmon_action_worker = SysmonActionWorker('install', self.config_manager)
            self._sysmon_action_worker.finished.connect(self._on_deploy_finished)
            self._sysmon_action_worker.start()

    def _on_deploy_finished(self, success, msg):
        self.btn_deploy.setEnabled(True)
        self.btn_deploy.setText("部署 Sysmon")
        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)
        self._update_status_display()

    def _uninstall_sysmon(self):
        info = self.config_manager.get_status_info()

        if not info['installed']:
            QMessageBox.information(self, "提示", "Sysmon 未安装，无需卸载")
            return

        if self._sysmon_action_worker and self._sysmon_action_worker.isRunning():
            QMessageBox.warning(self, "提示", "Sysmon 操作正在进行中，请稍候")
            return

        started_by_us = info.get('started_by_irtool', False)

        if started_by_us:
            msg = (
                "检测到 Sysmon 是由本工具安装的。\n\n"
                "卸载将：\n"
                "  • 停止 Sysmon 服务和驱动\n"
                "  • 移除 Sysmon 相关组件\n"
                "  • 已采集的日志数据不受影响\n\n"
                "是否确认卸载？"
            )
        else:
            msg = (
                "⚠ 检测到 Sysmon 非本工具安装，可能由其他安全软件或管理员部署。\n\n"
                "卸载将：\n"
                "  • 停止 Sysmon 服务和驱动\n"
                "  • 移除 Sysmon 相关组件\n"
                "  • 可能影响其他依赖 Sysmon 的安全工具\n\n"
                "是否确认卸载？"
            )

        reply = QMessageBox.warning(
            self,
            "确认卸载 Sysmon",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._is_collecting:
            self._stop_collection()

        self.btn_uninstall.setEnabled(False)
        self.btn_uninstall.setText("卸载中...")
        self._sysmon_action_worker = SysmonActionWorker('uninstall', self.config_manager)
        self._sysmon_action_worker.finished.connect(self._on_uninstall_finished)
        self._sysmon_action_worker.start()

    def _on_uninstall_finished(self, success, msg):
        self.btn_uninstall.setEnabled(True)
        self.btn_uninstall.setText("卸载 Sysmon")
        if success:
            self._sysmon_was_started_by_us = False
            QMessageBox.information(self, "卸载成功", msg)
        else:
            QMessageBox.warning(self, "卸载失败", msg)
        self._update_status_display()

    def _load_history_events(self):
        if not self.config_manager.is_installed():
            QMessageBox.warning(self, "提示", "Sysmon 未安装，无法加载历史事件")
            return

        if not self.config_manager.is_running():
            QMessageBox.warning(self, "提示", "Sysmon 服务未运行，无法读取日志")
            return

        temp_subscriber = SysmonSubscriber()
        if not temp_subscriber.is_sysmon_available():
            QMessageBox.warning(self, "提示", "无法连接到 Sysmon 日志通道")
            return

        # 禁用按钮，防止重复点击
        self.btn_load_history.setEnabled(False)
        self.btn_load_history.setText("加载中...")

        filter_external = self.chk_external_only.isChecked()
        worker = HistoryLoadWorker(temp_subscriber, limit=500, filter_external=filter_external)
        worker.finished.connect(lambda events: self._on_history_loaded(events, filter_external))
        self._history_load_worker = worker  # 持有引用，防止 GC
        worker.start()

    def _on_history_loaded(self, events: list, filter_external: bool):
        """后台加载完成后在主线程处理去重与 UI 更新"""
        # 恢复按钮
        self.btn_load_history.setEnabled(True)
        self.btn_load_history.setText("加载历史")

        def _make_event_key(ev):
            base_key = (
                getattr(ev, 'timestamp_epoch', 0),
                getattr(ev, 'event_id', 0),
                getattr(ev, 'process_id', getattr(ev, 'source_process_id', 0)),
            )
            if isinstance(ev, DnsEvent):
                return base_key + (ev.query_name,)
            elif isinstance(ev, NetworkConnectEvent):
                return base_key + (ev.destination_ip, ev.destination_port)
            elif isinstance(ev, CreateRemoteThreadEvent):
                return base_key + (ev.target_process_id, ev.start_address)
            elif isinstance(ev, FileCreateEvent):
                return base_key + (ev.target_filename,)
            return base_key

        existing_keys = set()
        for ev in self.all_events:
            existing_keys.add(_make_event_key(ev))

        new_events = []
        for ev in events:
            key = _make_event_key(ev)
            if key not in existing_keys:
                new_events.append(ev)
                existing_keys.add(key)

        if new_events:
            self.all_events = new_events + self.all_events
            self._pending_events = []

            rows = []
            sort_vals = []
            for event in self.all_events:
                row, sort_row = self._event_to_row(event)
                rows.append(row)
                sort_vals.append(sort_row)

            self._model.set_data_bulk(rows, sort_values=sort_vals)

            model_count = self._model.rowCount()
            if len(self.all_events) > model_count:
                self.all_events = self.all_events[len(self.all_events) - model_count:]

            self._proxy_model.set_events_data(self.all_events)

            self._apply_filters()

            self.lbl_events_count.setText(f"事件数: {len(self.all_events)}")

            self._resize_timer.start(100)

            filter_text = "（仅外连）" if filter_external else ""
            QMessageBox.information(self, "加载完成", f"已加载 {len(new_events)} 条新历史事件{filter_text}\n（已去重，跳过 {len(events) - len(new_events)} 条重复）")
        else:
            filter_text = "（仅外连）" if filter_external else ""
            QMessageBox.information(self, "提示", f"未找到新的历史事件{filter_text}（当前列表已包含所有历史）")

    def _clear_events(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._batch_update_timer.stop()
            self._pending_events = []
            self.all_events = []
            self._model.clear()
            self._proxy_model.set_events_data([])
            self.lbl_events_count.setText("事件数: 0")

            if self.data_store:
                self.data_store.clear_sysmon_events()

    def _export_events(self):
        if not self.all_events:
            QMessageBox.warning(self, "提示", "没有可导出的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出事件",
            f"sysmon_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON 文件 (*.json);;CSV 文件 (*.csv);;所有文件 (*)"
        )

        if not file_path:
            return

        data = [e.to_dict() for e in self.all_events]

        try:
            if file_path.endswith('.csv'):
                from utils.exporter import DataExporter
                exporter = DataExporter()
                if data:
                    columns = list(data[0].keys())
                    ok, msg = exporter.export_csv(data, file_path, columns)
                else:
                    ok, msg = False, "无数据"
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                ok, msg = True, f"已导出至: {file_path}"

            if ok:
                QMessageBox.information(self, "导出成功", msg)
            else:
                QMessageBox.warning(self, "导出失败", msg)
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _get_selected_event(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None, -1
        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)
        row = source_index.row()
        if 0 <= row < len(self.all_events):
            return self.all_events[row], row
        return None, -1

    def _show_context_menu(self, pos):
        event, _ = self._get_selected_event()
        if event is None:
            return

        menu = QMenu(self)

        # 根据不同事件类型添加不同的菜单项
        if isinstance(event, DnsEvent) and event.query_name:
            action_copy_domain = menu.addAction("复制域名")
            menu.addSeparator()
            action_search_vt = menu.addAction("VirusTotal 搜索域名")
        elif isinstance(event, NetworkConnectEvent):
            action_copy_dest_ip = menu.addAction("复制目标IP")
            action_copy_dest = menu.addAction("复制目标IP:端口")
            menu.addSeparator()
            action_search_vt_ip = menu.addAction("VirusTotal 搜索IP")
        elif isinstance(event, CreateRemoteThreadEvent):
            action_copy_source = menu.addAction("复制源进程路径")
            action_copy_target = menu.addAction("复制目标进程路径")
        elif isinstance(event, FileCreateEvent):
            action_copy_target_file = menu.addAction("复制文件路径")
            menu.addSeparator()
            action_open_target = menu.addAction("打开文件位置")

        action_copy_path = menu.addAction("复制进程路径")
        menu.addSeparator()
        action_open_path = menu.addAction("打开进程位置")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        clipboard = QApplication.clipboard()

        if isinstance(event, DnsEvent) and event.query_name:
            if action == action_copy_domain:
                clipboard.setText(event.query_name)
                return
            if action == action_search_vt:
                webbrowser.open(f"https://www.virustotal.com/gui/domain/{event.query_name}")
                return
        elif isinstance(event, NetworkConnectEvent):
            if action == action_copy_dest_ip:
                clipboard.setText(event.destination_ip)
                return
            if action == action_copy_dest:
                clipboard.setText(f"{event.destination_ip}:{event.destination_port}")
                return
            if action == action_search_vt_ip:
                webbrowser.open(f"https://www.virustotal.com/gui/ip-address/{event.destination_ip}")
                return
        elif isinstance(event, CreateRemoteThreadEvent):
            if action == action_copy_source:
                clipboard.setText(event.source_process_path)
                return
            if action == action_copy_target:
                clipboard.setText(event.target_process_path)
                return
        elif isinstance(event, FileCreateEvent):
            if action == action_copy_target_file:
                clipboard.setText(event.target_filename)
                return
            if action == action_open_target:
                self._open_file_location(event.target_filename)
                return

        if action == action_copy_path:
            if event.process_path:
                clipboard.setText(event.process_path)
        elif action == action_open_path:
            self._open_process_location(event)

    def _on_double_click(self, index):
        event, _ = self._get_selected_event()
        if not event:
            return

        clipboard = QApplication.clipboard()
        if isinstance(event, DnsEvent) and event.query_name:
            clipboard.setText(event.query_name)
        elif isinstance(event, NetworkConnectEvent):
            clipboard.setText(f"{event.destination_ip}:{event.destination_port}")
        elif isinstance(event, CreateRemoteThreadEvent):
            clipboard.setText(f"{event.source_process_name} -> {event.target_process_name}")
        elif isinstance(event, FileCreateEvent):
            clipboard.setText(event.target_filename)

    def _on_selection_changed(self, selected, deselected):
        event, _ = self._get_selected_event()
        if event:
            self._detail_panel.setHtml(self._format_event_detail(event))
            self._detail_container.show()
            pid = self._get_event_pid(event)
            if pid and pid > 0:
                self._process_tree_widget.show()
                self._process_tree_widget.load_pid(pid)
            else:
                self._process_tree_widget.hide()
                self._process_tree_widget.clear()
            self._btn_expand_detail.hide()
        else:
            self._detail_container.hide()
            self._process_tree_widget.hide()
            self._process_tree_widget.clear()

    def _close_detail_panels(self):
        self._detail_container.hide()
        self._process_tree_widget.hide()
        self._process_tree_widget.clear()
        self._position_expand_button()
        self._btn_expand_detail.show()

    def _expand_detail_panels(self):
        event, _ = self._get_selected_event()
        if not event:
            self._btn_expand_detail.hide()
            return
        self._detail_panel.setHtml(self._format_event_detail(event))
        self._detail_container.show()
        pid = self._get_event_pid(event)
        if pid and pid > 0:
            self._process_tree_widget.show()
            self._process_tree_widget.load_pid(pid)
        self._btn_expand_detail.hide()

    def _position_expand_button(self):
        self._btn_expand_detail.move(
            self.width() - 40,
            self.height() - 40
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._btn_expand_detail.isVisible():
            self._position_expand_button()

    @staticmethod
    def _get_event_pid(event) -> int:
        """提取事件中最有分析价值的 PID（发起方）。"""
        if isinstance(event, CreateRemoteThreadEvent):
            return event.source_process_id
        pid = getattr(event, 'process_id', 0)
        return int(pid) if pid else 0

    def _format_event_detail(self, event) -> str:
        rows = ""
        
        if isinstance(event, DnsEvent):
            fields = [
                ("事件类型", "DNS查询 (EventID 22)"),
                ("时间", event.timestamp),
                ("事件ID", str(event.event_id)),
                ("进程名", event.process_name),
                ("PID", str(event.process_id)),
                ("域名", event.query_name),
                ("查询结果", event.query_results or ""),
                ("查询状态", str(event.query_status)),
                ("用户", event.user),
                ("进程路径", event.process_path),
            ]
        elif isinstance(event, NetworkConnectEvent):
            external_status = "是 (外网IP)" if event.is_external else "否 (局域网)"
            fields = [
                ("事件类型", "网络连接 (EventID 3)"),
                ("时间", event.timestamp),
                ("事件ID", str(event.event_id)),
                ("进程名", event.process_name),
                ("PID", str(event.process_id)),
                ("源IP", event.source_ip),
                ("源端口", str(event.source_port)),
                ("目标IP", event.destination_ip),
                ("目标端口", str(event.destination_port)),
                ("是否外连", external_status),
                ("协议", event.protocol),
                ("主动连接", "是" if event.initiated else "否"),
                ("用户", event.user),
                ("进程路径", event.process_path),
            ]
        elif isinstance(event, CreateRemoteThreadEvent):
            suspicious_status = "是 (可疑注入)" if event.is_suspicious else "否"
            fields = [
                ("事件类型", "远程线程创建 (EventID 8)"),
                ("时间", event.timestamp),
                ("事件ID", str(event.event_id)),
                ("可疑标记", suspicious_status),
                ("源进程名", event.source_process_name),
                ("源PID", str(event.source_process_id)),
                ("目标进程名", event.target_process_name),
                ("目标PID", str(event.target_process_id)),
                ("新线程ID", str(event.new_thread_id)),
                ("起始地址", event.start_address),
                ("起始模块", event.start_module or ""),
                ("起始函数", event.start_function or ""),
                ("用户", event.user),
                ("源进程路径", event.source_process_path),
                ("目标进程路径", event.target_process_path),
            ]
        elif isinstance(event, FileCreateEvent):
            suspicious_status = "是 (可疑路径)" if event.is_suspicious else "否"
            fields = [
                ("事件类型", "DLL文件创建 (EventID 11)"),
                ("时间", event.timestamp),
                ("事件ID", str(event.event_id)),
                ("可疑标记", suspicious_status),
                ("进程名", event.process_name),
                ("PID", str(event.process_id)),
                ("目标文件", event.target_filename),
                ("创建时间(UTC)", event.creation_utc_time or ""),
                ("用户", event.user),
                ("进程路径", event.process_path),
            ]
        else:
            fields = [
                ("事件类型", f"其他 (EventID {event.event_id})"),
                ("时间", event.timestamp),
                ("事件ID", str(event.event_id)),
                ("进程名", getattr(event, 'process_name', '')),
                ("PID", str(getattr(event, 'process_id', 0))),
                ("用户", getattr(event, 'user', '')),
                ("进程路径", getattr(event, 'process_path', '')),
                ("原始数据", str(event.raw_data) if event.raw_data else ""),
            ]
        
        for label, value in fields:
            rows += f"<tr><td style='padding:4px 10px; color:#333; white-space:nowrap; vertical-align:top; font-weight:bold; font-size:14px;'>{label}</td><td style='padding:4px 10px; word-break:break-all; font-size:13px;'>{value}</td></tr>"
        return f"<table style='width:100%; border-collapse:collapse;'>{rows}</table>"

    def _open_process_location(self, event):
        if isinstance(event, CreateRemoteThreadEvent):
            path = event.source_process_path
        else:
            path = getattr(event, 'process_path', '')

        if not path or path.startswith("["):
            QMessageBox.warning(self, "提示", "进程路径不可用")
            return

        if os.path.isfile(path):
            subprocess.run(["explorer", "/select,", path], check=False)
        elif os.path.isdir(path):
            subprocess.run(["explorer", path], check=False)
        else:
            QMessageBox.warning(self, "提示", f"路径不存在: {path}")

    def _open_file_location(self, file_path: str):
        if not file_path or file_path.startswith("["):
            QMessageBox.warning(self, "提示", "文件路径不可用")
            return

        if os.path.isfile(file_path):
            subprocess.run(["explorer", "/select,", file_path], check=False)
        elif os.path.isdir(file_path):
            subprocess.run(["explorer", file_path], check=False)
        else:
            QMessageBox.warning(self, "提示", f"路径不存在: {file_path}")

    def stop_sysmon_if_started_by_us(self):
        if self._sysmon_was_started_by_us and self.config_manager.is_running():
            success, msg = self.config_manager.stop_service()
            if success:
                self.config_manager.clear_started_marker()
            else:
                logger.warning(f"停止Sysmon服务失败，保留标记文件以便下次重试: {msg}")
            self._sysmon_was_started_by_us = False

    def _check_crash_recovery(self):
        if self.config_manager.was_started_by_irtool():
            if self.config_manager.is_running():
                self._sysmon_was_started_by_us = True
            else:
                self.config_manager.clear_started_marker()

    def cleanup(self):
        self._batch_update_timer.stop()
        self._resize_timer.stop()
        self._stop_collection()
        self.stop_sysmon_if_started_by_us()
