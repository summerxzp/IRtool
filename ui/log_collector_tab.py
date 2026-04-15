from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QComboBox, QLabel,
    QMessageBox, QHeaderView, QLineEdit, QFrame,
    QGridLayout, QMenu, QFileDialog, QApplication,
    QSplitter, QTextEdit, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QSortFilterProxyModel
from PyQt6.QtGui import QColor
from datetime import datetime
import os
import subprocess
import json

from core.sysmon import (
    SysmonSubscriber, SysmonConfigManager,
    DnsEvent, SysmonEvent, NetworkConnectEvent, CreateRemoteThreadEvent, FileCreateEvent
)
from core.sysmon.config_manager import EVENT_CONFIG, DEFAULT_ENABLED_EVENTS
from ui.table_model import HighPerformanceTableModel
from ui.ui_style import apply_flat_style


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

    def set_event_type_filter(self, event_type: str):
        self._event_type_filter = event_type
        self.invalidateFilter()

    def set_external_only(self, external_only: bool):
        self._external_only = external_only
        self.invalidateFilter()

    def set_events_data(self, events: list):
        self._events_data = events
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        # 首先应用文本过滤
        if not super().filterAcceptsRow(source_row, source_parent):
            return False

        # 获取对应的事件对象
        if source_row < 0 or source_row >= len(self._events_data):
            return True

        event = self._events_data[source_row]

        # 事件类型筛选
        if self._event_type_filter != "全部":
            event_type_map = {
                "DNS查询": DnsEvent,
                "网络连接": NetworkConnectEvent,
                "远程线程": CreateRemoteThreadEvent,
                "DLL创建": FileCreateEvent,
            }
            expected_type = event_type_map.get(self._event_type_filter)
            if expected_type and not isinstance(event, expected_type):
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

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.btn_start = QPushButton("启动采集")
        self.btn_start.clicked.connect(self._toggle_collection)

        self.btn_deploy = QPushButton("部署 Sysmon")
        self.btn_deploy.clicked.connect(self._deploy_sysmon)

        self.btn_load_history = QPushButton("加载历史")
        self.btn_load_history.clicked.connect(self._load_history_events)

        self.btn_clear = QPushButton("清空记录")
        self.btn_clear.clicked.connect(self._clear_events)

        self.btn_export = QPushButton("导出")
        self.btn_export.clicked.connect(self._export_events)

        toolbar.addWidget(self.btn_start)
        toolbar.addWidget(self.btn_deploy)
        toolbar.addWidget(self.btn_load_history)
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_export)
        toolbar.addStretch()

        self.chk_external_only = QCheckBox("仅外连")
        self.chk_external_only.setToolTip("只显示外连事件（外网IP的网络连接和DNS查询）")
        self.chk_external_only.stateChanged.connect(self._on_external_only_changed)
        toolbar.addWidget(self.chk_external_only)

        layout.addLayout(toolbar)

        config_frame = QFrame()
        config_frame.setFrameShape(QFrame.Shape.Box)
        config_frame.setObjectName("panel")
        config_layout = QHBoxLayout(config_frame)
        config_layout.setContentsMargins(10, 4, 10, 4)

        config_layout.addWidget(QLabel("采集配置:"))

        self.event_checkboxes = {}
        for key, cfg in EVENT_CONFIG.items():
            cb = QCheckBox(cfg['name'])
            cb.setChecked(key in DEFAULT_ENABLED_EVENTS)
            cb.setToolTip(f"EventID {cfg['event_id']}")
            cb.stateChanged.connect(self._on_event_config_changed)
            config_layout.addWidget(cb)
            self.event_checkboxes[key] = cb

        self.btn_apply_config = QPushButton("应用配置")
        self.btn_apply_config.setToolTip("将当前勾选的采集配置应用到Sysmon")
        self.btn_apply_config.clicked.connect(self._apply_event_config)
        config_layout.addWidget(self.btn_apply_config)

        self.btn_open_config = QPushButton("打开配置")
        self.btn_open_config.setToolTip("打开配置文件所在目录")
        self.btn_open_config.clicked.connect(self._open_config_location)
        config_layout.addWidget(self.btn_open_config)

        config_layout.addStretch()
        layout.addWidget(config_frame)

        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.Box)
        status_frame.setObjectName("panel")
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
        self.event_type_filter = QComboBox()
        self.event_type_filter.addItems(["全部", "DNS查询", "网络连接", "远程线程", "DLL创建"])
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
        self.table.verticalHeader().setDefaultSectionSize(25)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.table.doubleClicked.connect(self._on_double_click)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        splitter.addWidget(self.table)

        self._detail_panel = QTextEdit()
        self._detail_panel.setReadOnly(True)
        self._detail_panel.setPlaceholderText("点击事件行查看详细信息...")
        self._detail_panel.setStyleSheet(
            "QTextEdit { background-color: #f8f8f8; border: 1px solid #ddd; "
            "border-radius: 4px; padding: 8px; font-family: 'Microsoft YaHei', 'Consolas', monospace; font-size: 13px; }"
        )
        self._detail_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._detail_panel.setMinimumHeight(100)
        self._detail_panel.setMaximumHeight(400)
        self._detail_panel.hide()

        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

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

        if info['installed'] and info['running']:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("启动采集")
        elif info['installed'] and not info['running']:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("启动采集 (需启动Sysmon)")

    def _toggle_collection(self):
        if self._is_collecting:
            self._stop_collection()
        else:
            self._start_collection()

    def _start_collection(self):
        if not self.config_manager.is_running():
            reply = QMessageBox.question(
                self,
                "Sysmon 未运行",
                "Sysmon 服务未运行，是否立即启动？\n\n"
                "注意：退出软件时会自动停止 Sysmon 服务。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                success, msg = self.config_manager.install()
                if not success:
                    QMessageBox.warning(self, "启动失败", msg)
                    return
                self._sysmon_was_started_by_us = True
                self.config_manager.mark_started_by_irtool()
                self._update_status_display()
            else:
                return
        else:
            self._sysmon_was_started_by_us = True
            self.config_manager.mark_started_by_irtool()

        filter_external = self.chk_external_only.isChecked()
        self.subscriber = SysmonSubscriber(filter_external_only=filter_external, enabled_events=self._enabled_events)

        if not self.subscriber.is_sysmon_available():
            QMessageBox.warning(
                self,
                "无法连接",
                "无法连接到 Sysmon 日志通道。\n请确认 Sysmon 已正确安装。"
            )
            self.subscriber = None
            return

        self.subscriber.event_received.connect(self._on_event_received)
        self.subscriber.status_changed.connect(self._on_status_changed)
        self.subscriber.error_occurred.connect(self._on_error)

        self.subscriber.start()

        self._is_collecting = True
        self._start_time = datetime.now()
        self.duration_timer.start(1000)

        self.btn_start.setText("停止采集")
        self.btn_start.setStyleSheet("background-color: #ffcccc;")

    def _stop_collection(self):
        if self.subscriber:
            self.subscriber.stop()
            self.subscriber = None

        self._is_collecting = False
        self._start_time = None
        self.duration_timer.stop()

        self.btn_start.setText("启动采集")
        self.btn_start.setStyleSheet("")

        self._update_status_label("disconnected")

    def _on_event_received(self, event):
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

        self._model.append_rows(new_rows, sort_values=new_sort_vals)

        # 更新代理模型的事件数据引用
        self._proxy_model.set_events_data(self.all_events)

        self._pending_events = []

        self._apply_filters()

        if not self._resize_timer.isActive() and self._model.rowCount() <= len(self._pending_events) + 50:
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
                event.process_name.lower(),
                event.process_id,
                "",
                event.query_name.lower(),
                event.user.lower(),
                event.process_path.lower(),
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
                event.process_name.lower(),
                event.process_id,
                "",
                f"{event.destination_ip}:{event.destination_port}".lower(),
                event.user.lower(),
                event.process_path.lower(),
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
                f"源:{event.source_process_path}\n目标:{event.target_process_path}",
            ]
            sort = [
                event.timestamp_epoch,
                "remote_thread",
                event.event_id,
                event.source_process_name.lower(),
                event.source_process_id,
                event.target_process_name.lower(),
                event.start_address.lower(),
                event.user.lower(),
                event.source_process_path.lower(),
            ]
        elif isinstance(event, FileCreateEvent):
            suspicious_mark = " [可疑路径]" if event.is_suspicious else ""
            display = [
                event.timestamp,
                f"DLL创建{suspicious_mark}",
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
                event.process_name.lower(),
                event.process_id,
                "",
                event.target_filename.lower(),
                event.user.lower(),
                event.process_path.lower(),
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

        if search_text or process_text:
            filter_parts = []
            if search_text:
                filter_parts.append(search_text)
            if process_text:
                filter_parts.append(process_text)
            self._proxy_model.setFilterFixedString(" ".join(filter_parts))
        else:
            self._proxy_model.setFilterFixedString("")

        # 更新事件数据引用
        self._proxy_model.set_events_data(self.all_events)

    def _on_event_type_changed(self, event_type: str):
        """事件类型筛选改变"""
        self._proxy_model.set_event_type_filter(event_type)
        self._apply_filters()

    def _on_external_only_changed(self, state):
        """仅外连筛选改变"""
        self._proxy_model.set_external_only(state == Qt.CheckState.Checked.value)

    def _on_event_config_changed(self):
        """采集配置复选框状态改变"""
        self._enabled_events = [
            key for key, cb in self.event_checkboxes.items() if cb.isChecked()
        ]

    def _apply_event_config(self):
        """应用采集配置到Sysmon"""
        enabled = [
            key for key, cb in self.event_checkboxes.items() if cb.isChecked()
        ]

        if not enabled:
            QMessageBox.warning(self, "提示", "至少需要启用一种事件类型")
            return

        if self._is_collecting:
            QMessageBox.warning(self, "提示", "请先停止采集再修改配置")
            return

        success, msg = self.config_manager.apply_config(enabled)
        if success:
            self._enabled_events = enabled
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def _open_config_location(self):
        """打开配置文件所在目录"""
        import subprocess
        import os

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

        if info['installed']:
            reply = QMessageBox.question(
                self,
                "Sysmon 已安装",
                "Sysmon 已安装，是否重新安装/更新配置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            success, msg = self.config_manager.update_config()
            if success:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失败", msg)
        else:
            success, msg = self.config_manager.install()
            if success:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失败", msg)

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

        existing_timestamps = set()
        for ev in self.all_events:
            ts = getattr(ev, 'timestamp_epoch', None)
            if ts:
                existing_timestamps.add(ts)

        filter_external = self.chk_external_only.isChecked()
        events = temp_subscriber.get_existing_events(limit=500, filter_external_only=filter_external)

        new_events = []
        for ev in events:
            ts = getattr(ev, 'timestamp_epoch', None)
            if ts and ts not in existing_timestamps:
                new_events.append(ev)
                existing_timestamps.add(ts)
            elif not ts:
                new_events.append(ev)

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

            # 更新代理模型的事件数据引用
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
                import webbrowser
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
                import webbrowser
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
            self._detail_panel.show()
        else:
            self._detail_panel.hide()

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
            self.config_manager.clear_started_marker()
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
