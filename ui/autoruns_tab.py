# ui/autoruns_tab.py
"""Autoruns 持久化检测标签页"""

# 标准库
import csv
import logging
import locale
import os
import subprocess
import uuid
from datetime import datetime

# 第三方库
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QTimer,
    QThread,
    QElapsedTimer,
)
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeView,
    QAbstractItemView,
    QCheckBox,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QLabel,
    QFrame,
    QSplitter,
    QTextEdit,
    QGridLayout,
    QScrollArea,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QApplication,
    QHeaderView,
)

# 本地模块
from core.risk_hint import RiskLevel
from core.signature_parser import parse_sigcheck_output
from ui.autoruns_tree_model import (
    TreeNode,
    AutorunsTreeModel,
    AutorunsFilterProxyModel,
)
from ui.autoruns_signature_worker import SignatureVerifyWorker
from ui.autoruns_detail_renderer import AutorunsDetailRenderer
from ui.autoruns_scan_controller import AutorunsScanController
from ui.dropdown_button import DropdownButton
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
    AUTORUNS_RISK_HELP_TEXT_STYLESHEET,
)


LOGGER = logging.getLogger("IRtool.autoruns_tab")
DEBUG_LOG_ENABLED = os.getenv("IRTOOL_DEBUG_LOG", "0") == "1"


def _debug_log(msg: str) -> None:
    """调试日志"""
    if DEBUG_LOG_ENABLED:
        LOGGER.debug(msg)


def get_app_dir() -> str:
    """获取应用根目录（支持源码运行和PyInstaller打包）"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(__file__))


def get_sigcheck_path() -> str:
    """获取sigcheck64.exe路径（支持源码和打包环境）"""
    base_dir = get_app_dir()
    possible_paths = [
        os.path.join(base_dir, "tools", "sigcheck64.exe"),
        os.path.join(base_dir, "_internal", "tools", "sigcheck64.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return possible_paths[0]  # 返回默认路径(如果不存在会报错)


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
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.btn_scan = QPushButton("▶ 开始扫描")
        self.btn_scan.setProperty("class", "primary")
        self.btn_scan.clicked.connect(self._start_scan)
        self.btn_scan.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)

        self.btn_cancel = QPushButton("取消扫描")
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)

        self.chk_hash = QCheckBox("计算Hash")
        self.chk_hash.setChecked(False)

        self.chk_sig = QCheckBox("验证签名")
        self.chk_sig.setChecked(False)  # Default to disabled
        
        self.cmb_category = DropdownButton()
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
        
        self.btn_delete = QPushButton("✕ 删除选中项")
        self.btn_delete.setProperty("class", "danger")
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)

        self.btn_export = QPushButton("↓ 导出CSV")
        self.btn_export.clicked.connect(self._export_csv)
        self.btn_export.setFixedHeight(AUTORUNS_CONTROL_HEIGHT)

        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_cancel)
        toolbar.addWidget(self.chk_hash)
        toolbar.addWidget(self.chk_sig)
        toolbar.addWidget(self.cmb_category)
        toolbar.addWidget(self.chk_suspicious)
        toolbar.addSpacing(12)
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
        
        # 设置样式：现代表格风格
        self.tree_view.setStyleSheet(
            AUTORUNS_TREE_STYLESHEET +
            "\nQTreeView { font-size: 13px; border: none; }"
            "\nQTreeView::item { min-height: 26px; padding-top: 2px; padding-bottom: 2px; }"
        )
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
        detail_layout.setSpacing(0)

        # Detail 标题栏（标题 + 关闭按钮）
        detail_title_bar = QWidget()
        detail_title_bar.setStyleSheet("background: transparent;")
        title_bar_layout = QHBoxLayout(detail_title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(0)

        detail_label = QLabel("详细信息")
        detail_label.setStyleSheet(AUTORUNS_DETAIL_TITLE_STYLESHEET)
        title_bar_layout.addWidget(detail_label)
        title_bar_layout.addStretch()

        self.btn_close_detail = QPushButton("✕")
        self.btn_close_detail.setFixedSize(24, 24)
        self.btn_close_detail.setToolTip("关闭详细信息")
        self.btn_close_detail.setStyleSheet(
            "QPushButton { border: 1px solid #c0c6d0; color: #555; font-size: 12px; "
            "background: #f0f2f5; border-radius: 4px; }"
            "QPushButton:hover { background: #e0e4ea; color: #333; border: 1px solid #a0a8b4; }"
            "QPushButton:pressed { background: #d0d4da; }"
        )
        self.btn_close_detail.clicked.connect(self._close_detail_pane)
        self.btn_close_detail.hide()
        title_bar_layout.addWidget(self.btn_close_detail)

        detail_layout.addWidget(detail_title_bar)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet(AUTORUNS_SCROLL_AREA_STYLESHEET)

        # Detail 内容容器（由 AutorunsDetailRenderer 自行管理布局）
        self.detail_widget = QWidget()
        self._detail_renderer = AutorunsDetailRenderer(
            splitter=self.splitter,
            detail_container=self.detail_widget,
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
        self.status_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.status_frame.setObjectName("stats-bar")
        # 设置较小的高度，只比字体高一点点
        font_metrics = self.fontMetrics()
        text_height = font_metrics.height()
        self.status_frame.setFixedHeight(text_height + 16)
        status_inner_layout = QHBoxLayout()
        status_inner_layout.setContentsMargins(8, 2, 8, 2)  # 减小上下边距，让按钮完整显示
        
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
        self.btn_help.setStyleSheet(
            "QPushButton { border: 1px solid #c0c6d0; color: #555; font-size: 12px; "
            "font-weight: 600; background: #f0f2f5; border-radius: 11px; }"
            "QPushButton:hover { background: #e0e4ea; color: #333; border: 1px solid #a0a8b4; }"
            "QPushButton:pressed { background: #d0d4da; }"
        )
        self.btn_help.clicked.connect(self._show_risk_help)
        status_inner_layout.addWidget(self.btn_help, alignment=Qt.AlignmentFlag.AlignVCenter)
        
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
        
        # Image Path：完整显示内容，可横向滚动
        self.tree_view.header().setStretchLastSection(False)
        self.tree_view.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    
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

        # 跳转到目标位置（根据条目类型自动选择跳转方式）
        location_str = str(data.get("location", ""))
        can_jump = self._can_jump_to_location(data)
        if can_jump:
            jump_label = self._get_jump_action_label(data)
            action_jump = menu.addAction(jump_label)
            action_jump.triggered.connect(lambda: self._jump_to_entry_location(data))
        
        menu.addSeparator()
        
        # 在工作台中搜索
        action_hunt = menu.addAction("在工作台中搜索")
        action_hunt.triggered.connect(lambda: self._search_in_workspace(data))
        
        # 显示菜单
        menu.exec(self.tree_view.viewport().mapToGlobal(pos))
    
    def _show_detail_placeholder(self):
        self._detail_renderer.show_placeholder()
        self.btn_close_detail.hide()

    def _close_detail_pane(self):
        self._detail_renderer.show_placeholder()
        self.btn_close_detail.hide()
        self.splitter.setSizes([1000, 0])

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
        self.btn_close_detail.show()
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
        entry_name = data.get('entry', '未知')
        LOGGER.info(f"[Hash] 开始计算 - 条目: {entry_name}, 路径: {image_path}")
        
        if not image_path or image_path.lower() == 'file not found':
            LOGGER.warning(f"[Hash] 失败 - 文件路径无效: {image_path}")
            QMessageBox.warning(self, "警告", "无法计算哈希：文件路径无效")
            return
        
        try:
            hash_result = self.parser.calculate_file_hash(image_path)
            md5 = hash_result.get('md5', '')
            sha256 = hash_result.get('sha256', '')
            
            LOGGER.info(f"[Hash] 成功 - MD5: {md5}, SHA256: {sha256[:32]}...")
            
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
            LOGGER.error(f"[Hash] 异常 - {e}")
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
        entry_name = data.get('entry', '未知')
        entry_id = data.get('id')
        
        LOGGER.info(f"[Signature] 请求验证 - 条目: {entry_name}, 路径: {image_path}")
        
        if not image_path or image_path.lower() == 'file not found':
            LOGGER.warning(f"[Signature] 失败 - 文件路径无效: {image_path}")
            QMessageBox.warning(self, "警告", "无法验证签名：文件路径无效")
            return

        if not entry_id:
            LOGGER.warning("[Signature] 失败 - 条目ID缺失")
            QMessageBox.warning(self, "警告", "无法验证签名：条目ID缺失")
            return

        sigcheck_path = get_sigcheck_path()
        if not os.path.exists(sigcheck_path):
            LOGGER.error(f"[Signature] 失败 - sigcheck64.exe 不存在: {sigcheck_path}")
            QMessageBox.warning(self, "警告", f"sigcheck64.exe 不存在: {sigcheck_path}")
            return

        running_worker = self._signature_workers_by_entry_id.get(entry_id)
        if running_worker and running_worker.isRunning():
            LOGGER.info(f"[Signature] 跳过 - 验证已在进行中: {entry_name}")
            QMessageBox.information(self, "提示", "该条目正在进行签名验证，请稍候。")
            return

        LOGGER.info(f"[Signature] 开始验证 - 条目: {entry_name}")
        
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
        LOGGER.info(f"[Explorer] 打开路径: {path}")
        try:
            import os
            if os.path.exists(path):
                if os.path.isdir(path):
                    subprocess.run(['explorer', path], check=False)
                else:
                    subprocess.run(['explorer', '/select,', path], check=False)
            else:
                LOGGER.warning(f"[Explorer] 路径不存在: {path}")
                QMessageBox.warning(self, "警告", f"文件不存在: {path}")
        except Exception as e:
            LOGGER.error(f"[Explorer] 异常: {e}")
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
        entry_name = data.get('entry', '')
        category = data.get('category', '')
        launch_string = data.get('launch_string', '')
        image_path = data.get('image_path', '')
        service_name = data.get('service_name', '')
        location = data.get('location', '')
        
        LOGGER.info(f"[Delete] 请求删除 - 条目: {entry_name}, 类型: {category}, 位置: {location}")
        
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
            LOGGER.info(f"[Delete] 用户取消删除 - 条目: {entry_name}")
            return
        
        LOGGER.info(f"[Delete] 开始执行删除 - 条目: {entry_name}")
        
        try:
            # 创建 AutorunEntry 对象
            from core.autoruns_parser import AutorunEntry
            entry = AutorunEntry(
                location=location,
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
            
            # 根据类型删除
            success, message = self.parser.delete_entry(entry)
            
            if success:
                LOGGER.info(f"[Delete] 成功 - 条目: {entry_name}, 消息: {message}")
                QMessageBox.information(self, "删除成功", message)
                
                # 从模型中移除该条目
                entry_id = data.get('id')
                removed = self.model.remove_node_by_id(entry_id) if entry_id else False
                if removed:
                    LOGGER.info(f"[Delete] 已从模型移除 - entry_id: {entry_id}")
                
                # 清空 Detail Pane
                self._show_detail_placeholder()
            else:
                LOGGER.warning(f"[Delete] 失败 - 条目: {entry_name}, 原因: {message}")
                self._show_delete_failure_dialog(data, message)
                
        except Exception as e:
            import traceback
            LOGGER.error(f"[Delete] 异常 - 条目: {entry_name}, 错误: {e}")
            LOGGER.error(f"[Delete] 堆栈:\n{traceback.format_exc()}")
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
<p style="color: #b8860b;">UI 表现：整行浅黄色强调，深金色字体，图标右下角黄色标记</p>

<p><b>🔴 高风险 (HIGH_RISK)</b></p>
<ul>
<li>Unsigned / 未验证签名条目</li>
<li>无签名 + 位于用户可写目录 (AppData / Temp / Downloads 等)</li>
<li>典型的恶意软件驻留路径</li>
</ul>
<p style="color: #8b0000;">UI 表现：整行浅红色强调，深红色字体，图标右下角红色标记</p>

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
        """精准打开计划任务的 XML 文件位置，若文件不存在则提供备选方案。"""
        xml_path = self._resolve_task_xml_path(data)
        task_entry = data.get("entry", "") or "未知"
        
        if not xml_path:
            # 无法解析路径，直接打开任务计划程序
            self._open_task_scheduler_gui(task_entry)
            return
        
        import os
        if os.path.exists(xml_path):
            try:
                subprocess.run(['explorer', '/select,', xml_path], check=False)
                return
            except Exception as exc:
                QMessageBox.warning(self, "打开失败", f"无法打开文件位置: {exc}")
        else:
            # XML 文件不存在，提供备选：打开任务计划程序 GUI
            dialog = QMessageBox(self)
            dialog.setWindowTitle("文件不存在")
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setText(
                f"任务 XML 文件不存在:\n{xml_path}\n\n"
                f"任务名: {task_entry}\n\n"
                "可能原因:\n"
                "- 任务存储在注册表中（旧版任务）\n"
                "- 任务已被删除\n"
                "- 权限不足"
            )
            
            btn_close = dialog.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
            btn_open_gui = dialog.addButton("打开任务计划程序", QMessageBox.ButtonRole.ActionRole)
            
            dialog.exec()
            
            if dialog.clickedButton() == btn_open_gui:
                self._open_task_scheduler_gui(task_entry)
    
    def _open_task_scheduler_gui(self, task_name=""):
        """打开任务计划程序 GUI，可选复制任务名到剪贴板。"""
        try:
            subprocess.run(["mmc.exe", "taskschd.msc"], check=False, shell=False)
            if task_name and task_name != "未知":
                from PyQt6.QtGui import QGuiApplication
                QGuiApplication.clipboard().setText(task_name)
                QMessageBox.information(
                    self,
                    "已打开任务计划程序",
                    f"任务计划程序已打开。\n\n任务名已复制到剪贴板:\n{task_name}\n\n"
                    "您可以在任务计划程序中粘贴搜索。"
                )
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"打开任务计划程序失败: {exc}")

    def _resolve_task_xml_path(self, data):
        """
        解析计划任务名称到 XML 文件的物理路径
        
        Windows 计划任务的存储位置:
        - 系统级: %SystemRoot%\\System32\\Tasks\\<task_name>.xml
        - 用户级: %AppData%\\Microsoft\\Windows\\Tasks\\<task_name>.xml (仅根级)
        
        entry 字段格式示例:
        - \\Track And Smooth          → Track And Smooth.xml
        - \\Microsoft\\Windows\\Update\\Scheduled Start → Microsoft/Windows/Update/Scheduled Start.xml
        """
        import os
        
        task_entry = (data.get("entry", "") or "").strip()
        _debug_log(f"[_resolve_task_xml_path] raw entry: {task_entry!r}")
        
        if not task_entry:
            _debug_log("[_resolve_task_xml_path] entry is empty, return None")
            return None
        
        # 移除前导反斜杠
        task_name = task_entry.lstrip('\\')
        _debug_log(f"[_resolve_task_xml_path] task_name after lstrip: {task_name!r}")
        
        if not task_name:
            _debug_log("[_resolve_task_xml_path] task_name is empty after lstrip, return None")
            return None
        
        # 如果 entry 已经包含 .xml 后缀，不再重复添加
        if task_name.lower().endswith('.xml'):
            xml_filename = task_name
            _debug_log(f"[_resolve_task_xml_path] entry already has .xml suffix")
        else:
            xml_filename = task_name + ".xml"
            _debug_log(f"[_resolve_task_xml_path] added .xml suffix: {xml_filename!r}")
        
        system_tasks_dir = os.path.join(
            os.environ.get('SystemRoot', r'C:\Windows'),
            'System32',
            'Tasks'
        )
        
        user_tasks_dir = os.path.join(
            os.environ.get('APPDATA', ''),
            'Microsoft',
            'Windows',
            'Tasks'
        )
        
        candidates = []
        
        system_path = os.path.join(system_tasks_dir, xml_filename.replace('\\', os.sep))
        candidates.append(system_path)
        _debug_log(f"[_resolve_task_xml_path] system candidate: {system_path}")
        
        if user_tasks_dir and os.path.isdir(os.path.dirname(user_tasks_dir)):
            user_path = os.path.join(user_tasks_dir, xml_filename.replace('\\', os.sep))
            if user_path != system_path:
                candidates.append(user_path)
                _debug_log(f"[_resolve_task_xml_path] user candidate: {user_path}")
        
        for path in candidates:
            if os.path.exists(path):
                _debug_log(f"[_resolve_task_xml_path] found existing file: {path}")
                return path
        
        _debug_log(f"[_resolve_task_xml_path] no existing file found, return first candidate: {candidates[0]}")
        return candidates[0] if candidates else None

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

    def _show_delete_failure_dialog(self, data, error_message):
        """删除失败时显示带"跳转到位置"按钮的对话框"""
        entry_name = data.get('entry', '') or '未知条目'
        category = data.get('category', '')
        
        can_jump = self._can_jump_to_location(data)
        jump_label = self._get_jump_action_label(data)
        
        msg = f"删除失败: {error_message}\n\n条目: {entry_name}\n类型: {category}"
        
        if can_jump:
            dialog = QMessageBox(self)
            dialog.setWindowTitle("删除失败")
            dialog.setIcon(QMessageBox.Icon.Warning)
            dialog.setText(msg)
            
            btn_close = dialog.addButton("关闭", QMessageBox.ButtonRole.RejectRole)
            btn_jump = dialog.addButton(jump_label, QMessageBox.ButtonRole.ActionRole)
            
            dialog.exec()
            
            if dialog.clickedButton() == btn_jump:
                self._jump_to_entry_location(data)
        else:
            QMessageBox.warning(self, "删除失败", msg)

    @staticmethod
    def _can_jump_to_location(data):
        """判断该条目是否支持跳转到位置"""
        location = str(data.get("location", ""))
        category = data.get("category", "")
        
        if category in ("Scheduled Tasks", "Tasks") or "Task" in location:
            return True
        if location and ("HKLM" in location or "HKCU" in location):
            return True
        if category == "Services":
            return True
        
        return False

    @staticmethod
    def _get_jump_action_label(data):
        """根据条目类型返回跳转按钮的文字"""
        location = str(data.get("location", ""))
        category = data.get("category", "")
        
        if category in ("Scheduled Tasks", "Tasks") or "Task" in location:
            return "跳转到任务文件"
        if category == "Services":
            return "打开服务管理器"
        return "跳转到注册表位置"

    def _jump_to_entry_location(self, data):
        """根据条目类型，精准跳转到目标位置（删除失败后的手动兜底）"""
        location = str(data.get("location", ""))
        category = data.get("category", "")
        entry_name = data.get("entry", "未知")
        
        LOGGER.info(f"[Jump] 请求跳转 - 条目: {entry_name}, 类型: {category}, 位置: {location}")
        
        try:
            if category in ("Scheduled Tasks", "Tasks") or "Task" in location:
                LOGGER.info(f"[Jump] 跳转到任务计划 - {entry_name}")
                self._open_task_scheduler_for_entry(data)
                return
            
            if category == "Services":
                LOGGER.info(f"[Jump] 打开服务管理器 - {entry_name}")
                subprocess.run(['services.msc'], check=False, shell=True)
                return
            
            if location and ("HKLM" in location or "HKCU" in location):
                LOGGER.info(f"[Jump] 跳转到注册表 - {location}")
                self._open_regedit_to_key(location)
                return
            
            LOGGER.warning(f"[Jump] 不支持的类型 - 条目: {entry_name}, 类型: {category}")
            QMessageBox.information(self, "提示", "此类型的条目暂不支持自动定位")
        except Exception as exc:
            LOGGER.error(f"[Jump] 失败 - 条目: {entry_name}, 错误: {exc}")
            QMessageBox.warning(self, "跳转失败", f"无法打开目标位置: {exc}")

    def _open_regedit_to_key(self, registry_path):
        """
        打开注册表编辑器并导航到指定键路径
        
        通过创建临时 .reg 文件并导入的方式实现精确定位，
        这是 Windows 上最可靠的 regedit 定位方法。
        """
        import tempfile
        
        escaped_path = registry_path.replace('\\', '\\\\')
        reg_content = f'Windows Registry Editor Version 5.00\n\n[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Applets\\Regedit]\n"LastKey"="{escaped_path}"\n'
        
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.reg')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                f.write(reg_content)
            
            subprocess.run(
                ['regedit', '/s', tmp_path],
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            subprocess.run(['regedit'], check=False)
        except Exception as exc:
            raise RuntimeError(f"打开注册表失败: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
