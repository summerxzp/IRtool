# ui/network_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QComboBox, QCheckBox,
    QMessageBox, QHeaderView, QFileDialog, QLineEdit, QLabel,
    QAbstractItemView, QFrame, QGridLayout, QMenu
)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor
import os
import subprocess
from utils.exporter import DataExporter
from datetime import datetime, timedelta
from ui.ui_style import apply_flat_style

class NumericTableWidgetItem(QTableWidgetItem):
    """自定义数值排序的TableWidgetItem，用于端口和PID的数值排序"""
    def __init__(self, text, sort_value=None):
        super().__init__(text)
        # 用于排序的数值，如果传入则使用，否则尝试从文本解析
        self.sort_value = sort_value if sort_value is not None else self._extract_numeric_value(text)
    
    def _extract_numeric_value(self, text):
        """提取文本中的数值用于排序"""
        if not text or text == "*":
            return float('-inf')  # 使"*"排在最后
        try:
            # 尝试转换为整数
            return int(text)
        except ValueError:
            try:
                # 如果不能转换为整数，尝试浮点数
                return float(text)
            except ValueError:
                # 如果都不是，返回负无穷大（排在最前面）
                return float('-inf')
    
    def __lt__(self, other):
        """重写比较运算符，实现数值排序"""
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        # 如果比较对象不是NumericTableWidgetItem，回退到字符串排序
        return self.text() < other.text()

class NetworkRefreshWorker(QThread):
    """后台刷新工作线程"""
    finished = pyqtSignal(list)
    
    def __init__(self, monitor, status_filter=None):
        super().__init__()
        self.monitor = monitor
        self.status_filter = status_filter
    
    def run(self):
        connections = self.monitor.get_connections(self.status_filter)
        self.finished.emit([c.to_dict() for c in connections])

class NetworkTab(QWidget):
    """网络监控标签页"""
    
    STATUS_COLORS = {
        'ESTABLISHED': QColor(144, 238, 144),  # 浅绿
        'LISTEN': QColor(173, 216, 230),        # 浅蓝
        'TIME_WAIT': QColor(255, 255, 224),     # 浅黄
        'CLOSE_WAIT': QColor(255, 182, 193),    # 浅红
    }
    HISTORY_COLOR = QColor(220, 220, 220)      # 历史记录背景灰色
    
    def __init__(self, network_monitor, data_store=None):
        super().__init__()
        apply_flat_style(self)
        self.monitor = network_monitor
        self.data_store = data_store
        self.current_data = []
        self.all_data = []
        self.filtered_data = []  # 添加过滤后的数据
        self.auto_refresh = True  # 默认开启自动刷新
        self.current_worker = None  # 当前正在运行的工作线程
        from datetime import datetime, timedelta
        
        self._last_search_text = ""  # 保存上次搜索文本
        self.refresh_interval = 1000  # 默认刷新间隔为1秒
        self._has_auto_resized = False  # 标记是否已经自动调整过列宽
        self._connection_cache = {}  # 连接历史缓存（仅UI层）
        self.history_retention_minutes = 10  # 历史记录保留时间（分钟），默认10分钟
        
        self._init_ui()
        self._init_timer()
    
    def _generate_connection_key(self, conn):
        """生成连接的唯一标识（PID + 五元组）"""
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
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(self.refresh_data)
        
        self.chk_auto_refresh = QCheckBox("自动刷新")
        self.chk_auto_refresh.setChecked(True)  # 默认勾选自动刷新
        self.chk_auto_refresh.stateChanged.connect(self._toggle_auto_refresh)
        
        # 刷新间隔选择
        refresh_interval_label = QLabel("刷新间隔:")
        self.cmb_refresh_interval = QComboBox()
        self.cmb_refresh_interval.addItems(["1秒", "2秒", "5秒"])
        self.cmb_refresh_interval.setCurrentIndex(0)  # 默认1秒
        self.cmb_refresh_interval.currentTextChanged.connect(self._on_refresh_interval_changed)
        

        
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["全部状态", "ESTABLISHED", "LISTEN", "TIME_WAIT", "CLOSE_WAIT", "NONE"])
        self.cmb_status.currentTextChanged.connect(self._on_status_filter_changed)  # 添加状态变化监听
        
        # 添加搜索框
        search_label = QLabel("搜索:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("PID/IP/端口/进程名")
        self.search_box.textChanged.connect(self._filter_table)
        
        self.btn_kill = QPushButton("终止进程")
        self.btn_kill.clicked.connect(self._kill_selected)
        
        self.btn_export = QPushButton("导出CSV")
        self.btn_export.clicked.connect(self._export_csv)
        
        self.btn_clear_history = QPushButton("清空记录")
        self.btn_clear_history.clicked.connect(self._clear_history)
        
        # 历史记录保留时间配置
        history_retention_label = QLabel("历史保留:")
        self.cmb_history_retention = QComboBox()
        self.cmb_history_retention.addItems(["1分钟", "5分钟", "10分钟", "持续保留"])
        self.cmb_history_retention.setCurrentIndex(2)  # 默认10分钟
        self.cmb_history_retention.currentTextChanged.connect(self._on_history_retention_changed)
        
        toolbar.addWidget(self.btn_refresh)
        toolbar.addWidget(self.chk_auto_refresh)
        toolbar.addWidget(refresh_interval_label)
        toolbar.addWidget(self.cmb_refresh_interval)
        toolbar.addWidget(self.cmb_status)
        toolbar.addSpacing(10)
        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_box, 1)  # 1表示拉伸因子
        toolbar.addStretch()
        toolbar.addWidget(self.btn_kill)
        toolbar.addWidget(self.btn_export)
        toolbar.addWidget(self.btn_clear_history)
        toolbar.addWidget(history_retention_label)
        toolbar.addWidget(self.cmb_history_retention)
        
        layout.addLayout(toolbar)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "时间", "PID", "进程名", "本地地址", 
            "本地端口", "远程地址", "远程端口", "状态", "协议", "进程路径"
        ])
        # 设置列宽自适应 - 混合模式（推荐）
        header = self.table.horizontalHeader()
        
        # 1. 先设置所有列允许用户手动拖拽 (基础模式)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # 2. 最后一列（进程路径）设置为自动拉伸，填满屏幕右侧空白
        last_column_index = self.table.columnCount() - 1
        if last_column_index >= 0:
            header.setSectionResizeMode(last_column_index, QHeaderView.ResizeMode.Stretch)
        
        # 启用列排序
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # 禁用表格编辑
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # 右键菜单
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        # 设置行高以确保内容完整显示
        self.table.verticalHeader().setDefaultSectionSize(25)  # 设置默认行高
        
        layout.addWidget(self.table)
        
        # 底部统计信息
        stats_layout = QHBoxLayout()
        
        # 创建统计标签
        self.stats_frame = QFrame()
        self.stats_frame.setFrameShape(QFrame.Shape.Box)
        self.stats_frame.setObjectName("panel")
        # 设置较小的高度，只比字体高一点点
        font_metrics = self.fontMetrics()
        text_height = font_metrics.height()
        self.stats_frame.setFixedHeight(text_height + 20)  # 比字体高一点点
        stats_inner_layout = QGridLayout()
        
        self.lbl_endpoints = QLabel("Endpoints: 0")
        self.lbl_established = QLabel("Established: 0")
        self.lbl_listening = QLabel("Listening: 0")
        self.lbl_time_wait = QLabel("Time Wait: 0")
        self.lbl_close_wait = QLabel("Close Wait: 0")
        self.lbl_history = QLabel("History: 0")
        
        # 修改布局为单行显示
        stats_inner_layout.addWidget(self.lbl_endpoints, 0, 0)
        stats_inner_layout.addWidget(self.lbl_established, 0, 1)
        stats_inner_layout.addWidget(self.lbl_listening, 0, 2)
        stats_inner_layout.addWidget(self.lbl_time_wait, 0, 3)
        stats_inner_layout.addWidget(self.lbl_close_wait, 0, 4)
        stats_inner_layout.addWidget(self.lbl_history, 0, 5)
        
        self.stats_frame.setLayout(stats_inner_layout)
        stats_layout.addWidget(self.stats_frame)
        
        layout.addLayout(stats_layout)
    
    def _init_timer(self):
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        
        # 如果默认开启自动刷新，则在此处启动定时器
        if self.auto_refresh:
            self._toggle_auto_refresh(2)  # 2表示Qt.Checked状态
    
    def _toggle_auto_refresh(self, state):
        self.auto_refresh = state == 2
        if self.auto_refresh:
            interval_index = self.cmb_refresh_interval.currentIndex()
            intervals = [1000, 2000, 5000]  # 对应 1秒, 2秒, 5秒
            interval = intervals[interval_index]
            self.refresh_timer.start(interval)
        else:
            self.refresh_timer.stop()
    
    def _on_refresh_interval_changed(self, text):
        """刷新间隔变化时触发"""
        if self.auto_refresh:
            # 如果正在自动刷新，立即应用新的间隔
            self._toggle_auto_refresh(2)  # 重新启动定时器
    
    def refresh_data(self):
        """刷新数据"""
        # 如果当前有正在运行的worker，则取消它
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        
        status_filter = None
        if self.cmb_status.currentIndex() > 0:
            status_filter = [self.cmb_status.currentText()]
        
        self.current_worker = NetworkRefreshWorker(self.monitor, status_filter)
        self.current_worker.finished.connect(self._on_data_received)
        self.current_worker.start()
    
    def _on_data_received(self, data):
        from datetime import datetime, timedelta
        now = datetime.now()

        # Process current connections
        current_keys = set()
        current_connections = []
        for conn in data:
            conn = conn.copy() 
            conn['is_current'] = True 
            key = self._generate_connection_key(conn)
            current_keys.add(key)
            if key in self._connection_cache:
                cached = self._connection_cache[key]
                cached.update(conn)
                current_connections.append(cached)
            else:
                self._connection_cache[key] = conn
                current_connections.append(conn)

        for key, cached in self._connection_cache.items():
            if key not in current_keys:
                cached['is_current'] = False

        # 清理超过保留时间的历史记录
        if self.history_retention_minutes > 0:
            retention_threshold = now - timedelta(minutes=self.history_retention_minutes)
            keys_to_remove = []
            for key, cached in self._connection_cache.items():
                if not cached.get('is_current', True):
                    conn_time = self._parse_connection_time(cached)
                    if conn_time and conn_time < retention_threshold:
                        keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._connection_cache[key]

        self.current_data = current_connections 
        self.all_data = list(self._connection_cache.values())
        if self.data_store:
            self.data_store.set_network_connections(self.current_data)

        # ========== 5. 搜索 / 状态过滤 ========== 
        self._apply_filters_and_update()
    
    def _apply_filters_and_update(self):
        text = self.search_box.text().strip().lower()

        data = self.all_data

        if text: 
            data = [ 
                c for c in data 
                if text in str(c['pid']).lower() 
                or text in str(c['process_name']).lower() 
                or text in str(c['process_path']).lower() 
                or text in str(c['local_address']).lower() 
                or text in str(c['remote_address']).lower() 
                or text in str(c['local_port']) 
                or text in str(c['remote_port']) 
            ] 

        if self.cmb_status.currentIndex() > 0: 
            status = self.cmb_status.currentText() 
            data = [c for c in data if c['status'] == status] 

        self.filtered_data = data 
        self._update_table(data) 
    
    def _filter_table(self, text):
        """根据文本过滤表格 - 修复逻辑缺陷，使用原始字段进行搜索"""
        # 保存当前搜索文本
        self._last_search_text = text
        
        # 重新应用过滤
        self._apply_filters_and_update()
    
    def _apply_status_filter(self):
        """应用状态筛选"""
        # 重新应用过滤
        self._apply_filters_and_update()
    
    def _on_status_filter_changed(self, text):
        """状态筛选变化时触发"""
        # 重新应用过滤
        self._apply_filters_and_update()
    
    def _update_table(self, data):
        """更新表格显示"""
        # 【修复点】：在更新数据前临时关闭排序，防止数据错位
        sorting_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        
        self.table.setRowCount(len(data))
        for row, conn in enumerate(data):
            is_current = conn.get('is_current', True)
            # 在UI层进行格式化显示
            formatted_local_addr = self._format_address_for_display(conn['local_address'])
            formatted_remote_addr = self._format_address_for_display(conn['remote_address'])
            # 对于远程端口，保留0的原始值，只对None或空字符串显示为*
            formatted_remote_port = str(conn['remote_port']) if conn['remote_port'] and conn['remote_port'] != "" else "*"
            
            items = [
                conn['timestamp'], 
                NumericTableWidgetItem(str(conn['pid']), conn['pid']),  # 使用数值排序的PID
                conn['process_name'],
                formatted_local_addr, 
                NumericTableWidgetItem(str(conn['local_port']), conn['local_port']),  # 使用数值排序的本地端口
                formatted_remote_addr, 
                NumericTableWidgetItem(formatted_remote_port, int(conn['remote_port']) if conn['remote_port'] and conn['remote_port'] != "" else None),  # 使用数值排序的远程端口
                conn['status'],
                conn['family'], 
                conn['process_path']
            ]
            for col, value in enumerate(items):
                item = value if isinstance(value, NumericTableWidgetItem) else QTableWidgetItem(value)
                
                # 检查进程是否已结束（进程名以[开头]结尾）
                # 修正：进程名列（col == 2）的值是字符串，可以直接检查
                if col == 2 and isinstance(item, QTableWidgetItem) and item.text().startswith("[") and item.text().endswith(" - 已结束]"):  # 进程名列
                    # 设置为灰色，表示进程已结束
                    item.setForeground(QColor(128, 128, 128))  # 灰色文字
                    item.setToolTip("此进程已结束，显示的是历史连接信息")
                
                if not is_current:
                    item.setBackground(self.HISTORY_COLOR)
                elif col == 7 and conn['status'] in self.STATUS_COLORS: 
                    item.setBackground(self.STATUS_COLORS[conn['status']])
                self.table.setItem(row, col, item)
        
        # 更新统计信息
        self._update_statistics(data)
        
        # 【新增】如果是第一次加载数据，自动调整列宽以适应内容
        if not self._has_auto_resized:  # 需要在 __init__ 里定义 self._has_auto_resized = False
            self.table.resizeColumnsToContents()
            # 再次强制最后一列拉伸（因为 resizeColumnsToContents 会覆盖掉 Stretch）
            header = self.table.horizontalHeader()
            last_col = self.table.columnCount() - 1
            header.setSectionResizeMode(last_col, QHeaderView.ResizeMode.Stretch)
            self._has_auto_resized = True
        
        # 【修复点】：数据更新完成后恢复排序状态
        self.table.setSortingEnabled(sorting_enabled)

    def _show_context_menu(self, pos):
        """显示右键菜单"""
        items = self.table.selectedItems()
        if not items:
            return

        menu = QMenu(self)
        action_open = menu.addAction("在资源管理器中打开")
        action_kill = menu.addAction("终止进程")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == action_open:
            self._open_selected_in_explorer()
        elif action == action_kill:
            self._kill_selected()

    def _open_selected_in_explorer(self):
        """在资源管理器中打开进程路径"""
        rows = sorted(set(item.row() for item in self.table.selectedItems()))
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择一条连接")
            return
        row = rows[0]
        path_item = self.table.item(row, 9)
        if not path_item:
            QMessageBox.warning(self, "提示", "无法获取进程路径")
            return
        path = path_item.text().strip()
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

    
    def _format_address_for_display(self, addr: str) -> str:
        """格式化地址用于显示，只对空字符串等特殊情况转换为*，保留0.0.0.0等原始值"""
        if addr in ["", "0.0.0.0", "::", "::ffff:0.0.0.0"]:
            return addr if addr != "" else "*"
        return addr

    def _parse_connection_time(self, conn: dict):
        """解析连接时间，兼容 epoch 与历史字符串格式"""
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
        """更新底部统计信息"""
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
        """终止选中的进程"""
        rows = set(item.row() for item in self.table.selectedItems())
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择要终止的连接")
            return
        
        # 添加确认弹窗
        reply = QMessageBox.question(
            self, 
            "确认终止", 
            f"确定要终止 {len(rows)} 个进程吗？", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        for row in rows:
            pid = int(self.table.item(row, 1).text())
            success, msg = self.monitor.kill_process(pid)
            if not success:
                QMessageBox.warning(self, "错误", msg)
        
        self.refresh_data()
    
    def _export_csv(self):
        """导出CSV"""
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
        """历史记录保留时间变化时触发"""
        retention_map = {
            "1分钟": 1,
            "5分钟": 5,
            "10分钟": 10,
            "持续保留": 0
        }
        self.history_retention_minutes = retention_map.get(text, 10)
        # 立即清理过期的历史记录
        self.refresh_data()
    
    def _clear_history(self):
        """清空所有历史记录"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 只保留当前活跃的连接，清空历史记录
            keys_to_remove = []
            for key, cached in self._connection_cache.items():
                if not cached.get('is_current', True):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._connection_cache[key]
            
            # 刷新显示
            self.refresh_data()
            QMessageBox.information(self, "提示", "历史记录已清空")
