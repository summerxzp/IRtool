from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QCheckBox,
    QMessageBox, QHeaderView, QFileDialog, QLineEdit, QLabel,
    QFrame, QGridLayout, QMenu
)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt, QSortFilterProxyModel, QModelIndex
from PyQt6.QtGui import QColor
import os
import subprocess
from utils.exporter import DataExporter
from datetime import datetime, timedelta
from ui.ui_style import apply_flat_style
from ui.table_model import HighPerformanceTableModel
from ui.dropdown_button import DropdownButton


NET_COLUMNS = [
    "时间", "PID", "进程名", "本地地址",
    "本地端口", "远程地址", "远程端口", "状态", "协议", "进程路径"
]

STATUS_COLORS = {
    'ESTABLISHED': QColor(144, 238, 144),
    'LISTEN': QColor(173, 216, 230),
    'TIME_WAIT': QColor(255, 255, 224),
    'CLOSE_WAIT': QColor(255, 182, 193),
}
HISTORY_COLOR = QColor(220, 220, 220)


class NetworkTableModel(HighPerformanceTableModel):
    def __init__(self, parent=None):
        super().__init__(NET_COLUMNS, parent)


class NetworkRefreshWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, monitor, status_filter=None):
        super().__init__()
        self.monitor = monitor
        self.status_filter = status_filter

    def run(self):
        connections = self.monitor.get_connections(self.status_filter)
        self.finished.emit([c.to_dict() for c in connections])


class NetworkTab(QWidget):

    def __init__(self, network_monitor, data_store=None):
        super().__init__()
        apply_flat_style(self)
        self.monitor = network_monitor
        self.data_store = data_store
        self.current_data = []
        self.all_data = []
        self.auto_refresh = True
        self.current_worker = None
        self._refresh_pending = False
        self._refresh_generation = 0
        self._ui_refresh_paused = False
        self._paused_refresh_payload = None

        self.refresh_interval = 1000
        self._has_auto_resized = False
        self._connection_cache = {}
        self.history_retention_minutes = 10

        self._init_ui()
        self._init_timer()

    def _generate_connection_key(self, conn):
        return (
            conn['pid'],
            conn['local_address'],
            conn['local_port'],
            conn['remote_address'],
            conn['remote_port'],
            conn['family']
        )

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_refresh = QPushButton("↻ 刷新")
        self.btn_refresh.setProperty("class", "primary")
        self.btn_refresh.clicked.connect(self.refresh_data)

        self.chk_auto_refresh = QCheckBox("自动刷新")
        self.chk_auto_refresh.setChecked(True)
        self.chk_auto_refresh.stateChanged.connect(self._toggle_auto_refresh)

        refresh_interval_label = QLabel("刷新间隔:")
        self.cmb_refresh_interval = DropdownButton()
        self.cmb_refresh_interval.addItems(["1秒", "2秒", "5秒"])
        self.cmb_refresh_interval.setCurrentIndex(0)
        self.cmb_refresh_interval.currentTextChanged.connect(self._on_refresh_interval_changed)

        self.cmb_status = DropdownButton()
        self.cmb_status.addItems(["全部状态", "ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT", "NONE"])
        self.cmb_status.currentTextChanged.connect(self._on_status_filter_changed)

        search_label = QLabel("搜索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("PID / IP / 端口 / 进程名")
        self.search_box.textChanged.connect(self._on_search_debounced)

        self.btn_kill = QPushButton("✕ 终止进程")
        self.btn_kill.setProperty("class", "danger")
        self.btn_kill.clicked.connect(self._kill_selected)

        self.btn_export = QPushButton("↓ 导出CSV")
        self.btn_export.clicked.connect(self._export_csv)

        self.btn_clear_history = QPushButton("清空记录")
        self.btn_clear_history.setProperty("class", "danger")
        self.btn_clear_history.clicked.connect(self._clear_history)

        history_retention_label = QLabel("历史保留:")
        self.cmb_history_retention = DropdownButton()
        self.cmb_history_retention.addItems(["1分钟", "5分钟", "10分钟", "持续保留"])
        self.cmb_history_retention.setCurrentIndex(2)
        self.cmb_history_retention.currentTextChanged.connect(self._on_history_retention_changed)

        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.chk_auto_refresh)
        toolbar.addWidget(refresh_interval_label)
        toolbar.addWidget(self.cmb_refresh_interval)
        toolbar.addWidget(self.cmb_status)
        toolbar.addSpacing(12)
        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_box, 1)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_kill)
        toolbar.addWidget(self.btn_export)
        toolbar.addWidget(self.btn_clear_history)
        toolbar.addSpacing(8)
        toolbar.addWidget(history_retention_label)
        toolbar.addWidget(self.cmb_history_retention)

        layout.addLayout(toolbar)

        self._model = NetworkTableModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setSortRole(Qt.ItemDataRole.EditRole)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)

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

        layout.addWidget(self.table)

        self.stats_frame = QFrame()
        self.stats_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.stats_frame.setObjectName("stats-bar")
        font_metrics = self.fontMetrics()
        text_height = font_metrics.height()
        self.stats_frame.setFixedHeight(text_height + 18)
        stats_inner_layout = QGridLayout()
        stats_inner_layout.setContentsMargins(12, 4, 12, 4)
        stats_inner_layout.setHorizontalSpacing(20)

        self.lbl_endpoints = QLabel("Endpoints: 0")
        self.lbl_established = QLabel("Established: 0")
        self.lbl_established.setStyleSheet("color: #2e7d32; font-weight: 500;")
        self.lbl_listening = QLabel("Listening: 0")
        self.lbl_listening.setStyleSheet("color: #1565c0; font-weight: 500;")
        self.lbl_time_wait = QLabel("Time Wait: 0")
        self.lbl_time_wait.setStyleSheet("color: #f9a825; font-weight: 500;")
        self.lbl_close_wait = QLabel("Close Wait: 0")
        self.lbl_close_wait.setStyleSheet("color: #c62828; font-weight: 500;")
        self.lbl_history = QLabel("History: 0")
        self.lbl_history.setStyleSheet("color: #9e9e9e;")

        stats_inner_layout.addWidget(self.lbl_endpoints, 0, 0)
        stats_inner_layout.addWidget(self.lbl_established, 0, 1)
        stats_inner_layout.addWidget(self.lbl_listening, 0, 2)
        stats_inner_layout.addWidget(self.lbl_time_wait, 0, 3)
        stats_inner_layout.addWidget(self.lbl_close_wait, 0, 4)
        stats_inner_layout.addWidget(self.lbl_history, 0, 5)

        self.stats_frame.setLayout(stats_inner_layout)
        layout.addWidget(self.stats_frame)

        self._search_debounce_timer = QTimer()
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._apply_filters_and_update)

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_auto_resize)

    def _on_search_debounced(self):
        self._search_debounce_timer.start(200)

    def _do_auto_resize(self):
        self.table.resizeColumnsToContents()

    def _init_timer(self):
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        if self.auto_refresh:
            self._toggle_auto_refresh(2)

    def _toggle_auto_refresh(self, state):
        self.auto_refresh = state == 2
        if self.auto_refresh:
            interval_index = self.cmb_refresh_interval.currentIndex()
            intervals = [1000, 2000, 5000]
            interval = intervals[interval_index]
            self.refresh_timer.start(interval)
        else:
            self.refresh_timer.stop()

    def _on_refresh_interval_changed(self, text):
        if self.auto_refresh:
            self._toggle_auto_refresh(2)

    def refresh_data(self):
        if self._ui_refresh_paused:
            self._refresh_pending = True
            return

        if self.current_worker and self.current_worker.isRunning():
            self._refresh_pending = True
            return

        status_filter = None
        if self.cmb_status.currentIndex() > 0:
            status_filter = [self.cmb_status.currentText()]

        self._refresh_generation += 1
        self.current_worker = NetworkRefreshWorker(self.monitor, status_filter)
        request_generation = self._refresh_generation
        self.current_worker.finished.connect(
            lambda data, generation=request_generation: self._on_data_received(data, generation)
        )
        self.current_worker.start()

    def _build_search_blob(self, conn):
        return (
            f"{conn['pid']}|{conn['process_name']}|{conn['process_path']}|"
            f"{conn['local_address']}|{conn['remote_address']}|"
            f"{conn['local_port']}|{conn['remote_port']}"
        ).lower()

    def _on_data_received(self, data, generation=None):
        if generation is not None and generation != self._refresh_generation:
            return
        if self._ui_refresh_paused:
            self._paused_refresh_payload = data
            self.current_worker = None
            return

        now = datetime.now()

        current_keys = set()
        current_connections = []
        cache_changed = False
        for conn in data:
            key = self._generate_connection_key(conn)
            current_keys.add(key)
            if key in self._connection_cache:
                cached = self._connection_cache[key]
                cached['last_seen_epoch'] = conn['last_seen_epoch']
                cached['timestamp'] = conn['timestamp']
                cached['timestamp_epoch'] = conn['timestamp_epoch']
                cached['status'] = conn['status']
                was_current = cached.get('is_current', True)
                cached['is_current'] = True
                if not was_current:
                    cache_changed = True
                current_connections.append(cached)
            else:
                conn['is_current'] = True
                conn['_search_blob'] = self._build_search_blob(conn)
                self._connection_cache[key] = conn
                current_connections.append(conn)
                cache_changed = True

        for key, cached in self._connection_cache.items():
            if key not in current_keys:
                if cached.get('is_current', True):
                    cached['is_current'] = False
                    cache_changed = True

        if self.history_retention_minutes > 0:
            retention_threshold = now - timedelta(minutes=self.history_retention_minutes)
            keys_to_remove = []
            for key, cached in self._connection_cache.items():
                if not cached.get('is_current', True):
                    last_seen = cached.get('last_seen_epoch')
                    if last_seen:
                        try:
                            last_seen_dt = datetime.fromtimestamp(last_seen)
                            if last_seen_dt < retention_threshold:
                                keys_to_remove.append(key)
                        except (OverflowError, OSError, ValueError):
                            pass
                    else:
                        conn_time = self._parse_connection_time(cached)
                        if conn_time and conn_time < retention_threshold:
                            keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._connection_cache[key]
                cache_changed = True

        self.current_data = current_connections
        if cache_changed or not self.all_data:
            self.all_data = list(self._connection_cache.values())
        if self.data_store:
            self.data_store.set_network_connections(
                current_connections=self.current_data,
                history_connections=self.all_data,
            )

        self._apply_filters_and_update()

        self.current_worker = None
        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_data)

    def _apply_filters_and_update(self):
        selected_key = self._get_selected_connection_key()
        text = self.search_box.text().strip().lower()
        data = self.all_data

        if text:
            data = [
                c for c in data
                if text in c.get('_search_blob', self._build_search_blob(c))
            ]

        if self.cmb_status.currentIndex() > 0:
            status = self.cmb_status.currentText()
            data = [c for c in data if c['status'] == status]

        self._update_model(data)
        self._update_statistics(data)
        self._restore_selection(selected_key)

    def _filter_table(self, text):
        self._apply_filters_and_update()

    def _apply_status_filter(self):
        self._apply_filters_and_update()

    def _on_status_filter_changed(self, text):
        self._apply_filters_and_update()

    def _update_model(self, data):
        new_row_count = min(len(data), self._model.MAX_ROWS)
        if (self._model.row_count_matches(new_row_count)
                and not self.search_box.text().strip()
                and self.cmb_status.currentIndex() == 0):
            changed = False
            for i, conn in enumerate(data):
                if i >= new_row_count:
                    break
                is_current = conn.get('is_current', True)
                old_bg = self._model._backgrounds[i][7] if i < len(self._model._backgrounds) else None
                new_bg = None
                if not is_current:
                    new_bg = HISTORY_COLOR
                elif conn['status'] in STATUS_COLORS:
                    new_bg = STATUS_COLORS[conn['status']]
                if old_bg != new_bg:
                    changed = True
                    break
            if not changed:
                return

        rows = []
        sort_vals = []
        backgrounds = []
        foregrounds = []
        tooltips = []

        for conn in data:
            is_current = conn.get('is_current', True)
            formatted_local_addr = self._format_address_for_display(conn['local_address'])
            formatted_remote_addr = self._format_address_for_display(conn['remote_address'])
            formatted_remote_port = str(conn['remote_port']) if conn['remote_port'] and conn['remote_port'] != "" else "*"

            remote_port_sort = int(conn['remote_port']) if conn['remote_port'] and conn['remote_port'] != "" else -1

            first_seen = conn.get('first_seen_epoch')
            if first_seen and first_seen > 0:
                try:
                    display_time = datetime.fromtimestamp(first_seen).strftime("%Y/%m/%d %H:%M:%S")
                except (OverflowError, OSError, ValueError):
                    display_time = conn['timestamp']
            else:
                display_time = conn['timestamp']

            row = [
                display_time,
                str(conn['pid']),
                conn['process_name'],
                formatted_local_addr,
                str(conn['local_port']),
                formatted_remote_addr,
                formatted_remote_port,
                conn['status'],
                conn['family'],
                conn['process_path'],
            ]
            sort_row = [
                conn.get('timestamp_epoch', 0),
                conn['pid'],
                conn['process_name'].lower(),
                formatted_local_addr.lower(),
                conn['local_port'],
                formatted_remote_addr.lower(),
                remote_port_sort,
                conn['status'],
                conn['family'],
                conn['process_path'].lower(),
            ]

            row_bgs = [None] * len(NET_COLUMNS)
            row_fgs = [None] * len(NET_COLUMNS)
            row_tips = [None] * len(NET_COLUMNS)

            if not is_current:
                row_bgs = [HISTORY_COLOR] * len(NET_COLUMNS)
            elif conn['status'] in STATUS_COLORS:
                row_bgs[7] = STATUS_COLORS[conn['status']]

            if conn['process_name'].startswith("[") and conn['process_name'].endswith(" - 已结束]"):
                row_fgs[2] = QColor(128, 128, 128)
                row_tips[2] = "此进程已结束，显示的是历史连接信息"

            rows.append(row)
            sort_vals.append(sort_row)
            backgrounds.append(row_bgs)
            foregrounds.append(row_fgs)
            tooltips.append(row_tips)

        self._model.set_data_bulk(rows, sort_values=sort_vals,
                                  backgrounds=backgrounds,
                                  foregrounds=foregrounds,
                                  tooltips=tooltips)
        if not self._has_auto_resized:
            self._resize_timer.start(100)
            self._has_auto_resized = True

    def _get_selected_connection_key(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)
        row_data = self._model.get_row_data(source_index.row())
        if not row_data:
            return None
        # row_data 顺序：时间, PID, 进程名, 本地地址, 本地端口, 远程地址, 远程端口, 状态, 协议, 进程路径
        return (row_data[1], row_data[4], row_data[5], row_data[6])  # pid, local_port, remote_addr, remote_port

    def _restore_selection(self, connection_key):
        if connection_key is None:
            return
        for proxy_row in range(self._proxy_model.rowCount()):
            source_index = self._proxy_model.mapToSource(self._proxy_model.index(proxy_row, 0))
            row_data = self._model.get_row_data(source_index.row())
            if row_data:
                key = (row_data[1], row_data[4], row_data[5], row_data[6])
                if key == connection_key:
                    self.table.selectRow(proxy_row)
                    self.table.scrollTo(self._proxy_model.index(proxy_row, 0),
                                       QTableView.ScrollHint.EnsureVisible)
                    return

    def _set_ui_refresh_paused(self, paused: bool):
        was_paused = self._ui_refresh_paused
        self._ui_refresh_paused = paused
        if paused or was_paused == paused:
            return

        if self._paused_refresh_payload is not None:
            payload = self._paused_refresh_payload
            self._paused_refresh_payload = None
            self._on_data_received(payload, self._refresh_generation)
            return

        if self._refresh_pending:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_data)

    def _show_context_menu(self, pos):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return

        was_auto_refresh = self.refresh_timer.isActive()
        self._set_ui_refresh_paused(True)
        self.refresh_timer.stop()

        menu = QMenu(self)
        action_open = menu.addAction("在资源管理器中打开")
        action_kill = menu.addAction("终止进程")
        menu.addSeparator()
        action_ptree = menu.addAction("查看父进程链")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        self._set_ui_refresh_paused(False)
        if was_auto_refresh and self.auto_refresh:
            self._toggle_auto_refresh(2)

        if action == action_open:
            self._open_selected_in_explorer()
        elif action == action_kill:
            self._kill_selected()
        elif action == action_ptree:
            self._show_process_tree_dialog()

    def _get_selected_row_data(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        proxy_index = indexes[0]
        source_index = self._proxy_model.mapToSource(proxy_index)
        row = source_index.row()
        return self._model.get_row_data(row)

    def _open_selected_in_explorer(self):
        row_data = self._get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "提示", "请先选择一条连接")
            return
        path = row_data[9].strip()
        if not path or path.startswith("["):
            QMessageBox.warning(self, "提示", "进程路径不可用")
            return
        if os.path.isdir(path):
            subprocess.run(["explorer", path], check=False)
            return
        if os.path.isfile(path):
            subprocess.run(["explorer", "/select,", path], check=False)
            return
        QMessageBox.warning(self, "提示", f"路径不存在: {path}")

    def _show_process_tree_dialog(self):
        row_data = self._get_selected_row_data()
        if not row_data:
            return
        try:
            pid = int(row_data[1])
        except (TypeError, ValueError):
            QMessageBox.warning(self, "提示", "无法获取 PID")
            return

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
        from ui.process_tree_widget import ProcessTreeWidget

        dlg = QDialog(self)
        dlg.setWindowTitle(f"父进程链 — {row_data[2]} (PID: {pid})")
        dlg.resize(600, 260)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(8, 8, 8, 8)

        tree = ProcessTreeWidget(dlg)
        tree.load_pid(pid)
        layout.addWidget(tree)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        dlg.exec()

    def _format_address_for_display(self, addr: str) -> str:
        if addr in ["", "0.0.0.0", "::", "::ffff:0.0.0.0"]:
            return addr if addr != "" else "*"
        return addr

    def _parse_connection_time(self, conn: dict):
        ts_epoch = conn.get('timestamp_epoch')
        if isinstance(ts_epoch, (int, float)):
            try:
                return datetime.fromtimestamp(ts_epoch)
            except (OverflowError, OSError, ValueError):
                pass

        ts_text = conn.get('timestamp')
        if not ts_text:
            return None

        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
            try:
                return datetime.strptime(str(ts_text), fmt)
            except (ValueError, TypeError):
                continue
        return None

    def _update_statistics(self, data):
        total_endpoints = len(data)
        established_count = sum(1 for conn in data if conn['status'] == 'ESTABLISHED')
        listening_count = sum(1 for conn in data if conn['status'] == 'LISTEN')
        time_wait_count = sum(1 for conn in data if conn['status'] == 'TIME_WAIT')
        close_wait_count = sum(1 for conn in data if conn['status'] == 'CLOSE_WAIT')
        history_count = sum(1 for conn in data if not conn.get('is_current', True))

        self.lbl_endpoints.setText(f"Endpoints: {total_endpoints}")
        self.lbl_established.setText(f"Established: {established_count}")
        self.lbl_listening.setText(f"Listening: {listening_count}")
        self.lbl_time_wait.setText(f"Time Wait: {time_wait_count}")
        self.lbl_close_wait.setText(f"Close Wait: {close_wait_count}")
        self.lbl_history.setText(f"History: {history_count}")

    def _kill_selected(self):
        row_data = self._get_selected_row_data()
        if not row_data:
            QMessageBox.warning(self, "提示", "请先选择要终止的连接")
            return

        pid = int(row_data[1])

        reply = QMessageBox.question(
            self,
            "确认终止",
            f"确定要终止 PID {pid} 的进程吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        success, msg = self.monitor.kill_process(pid)
        if not success:
            QMessageBox.warning(self, "错误", msg)

        self.refresh_data()

    def _export_csv(self):
        data_to_export = self.all_data if self.all_data else self.current_data
        if not data_to_export:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出CSV", "", "CSV文件 (*.csv);;所有文件 (*)"
        )

        if file_path:
            columns = [
                "timestamp", "pid", "process_name", "process_path",
                "local_address", "local_port", "remote_address",
                "remote_port", "status", "family"
            ]
            success, msg = DataExporter.export_csv(data_to_export, file_path, columns)

            if success:
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "错误", msg)

    def _on_history_retention_changed(self, text):
        retention_map = {
            "1分钟": 1,
            "5分钟": 5,
            "10分钟": 10,
            "持续保留": 0
        }
        self.history_retention_minutes = retention_map.get(text, 10)
        self.refresh_data()

    def _clear_history(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            keys_to_remove = []
            for key, cached in self._connection_cache.items():
                if not cached.get('is_current', True):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._connection_cache[key]

            self.refresh_data()
            QMessageBox.information(self, "提示", "历史记录已清空")
